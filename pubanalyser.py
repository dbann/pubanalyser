import streamlit as st
import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pyalex
from pyalex import Author, Authors, Work, Works, Publisher, Publishers, Institution, Institutions
from rich import print
from itertools import chain
from streamlit.logger import get_logger
from constants import USER_EMAIL, FOR_PROFIT_PUBLISHERS, PREPRINT_SERVERS, ESTIMATED_APC, PUBLISHER_NAME_MAPPING, COMPANY_ABBREVIATIONS, MAX_NUM

_LOGGER = get_logger(__name__)

# Setup pyalex
pyalex.config.email = USER_EMAIL
pyalex.config.max_retries = 5
pyalex.config.retry_backoff_factor = 0.2
pyalex.config.retry_http_codes = [429, 500, 503]


def get_author_by_id(identifier: str) -> tuple[Author, str | None]:
    """Get author details for an ORCID or OpenAlex author ID via OpenAlex API."""
    try:
        author: Author = Authors()[identifier]
        return author, clean_author_id(author.get('id', None))
    except Exception as e:
        print(f"Error in get_author_by_id: {str(e)}")
        return {}, None


def search_authors(query: str) -> list[Author | None]:
    """Search for authors using OpenAlex API."""
    try:
        oa_query = Authors().search(query)
        authors = []
        for record in chain(*oa_query.paginate(per_page=200)):
            authors.append(record)
        return authors
    except Exception as e:
        print(f"Error in search_authors: {str(e)}")
        return []


def clean_author_id(author_id: str) -> str | None:
    """Clean and format the author ID."""
    if not author_id or not isinstance(author_id, str):
        return None
    if '/' in author_id:
        author_id = author_id.split('/')[-1]
    author_id = author_id.lstrip('Aa')
    return f"A{author_id}"


def fetch_publications(author: Author) -> list[Work | None]:
    """Fetch publications data for an author from OpenAlex API."""
    with st.spinner('Fetching publication data...'):
        try:
            query = Works().filter(author={"id": author.get('id')})
            results = []
            for record in chain(*query.paginate(per_page=200)):
                results.append(record)
            return results
        except Exception as e:
            print(f"Error in fetch_publications: {str(e)}")
            return []


def get_publishers_by_ids(publisher_ids: set[str]) -> list[Publisher | None]:
    if len(publisher_ids) == 0:
        return []
    try:
        return [Publishers()[publisher_id] for publisher_id in publisher_ids]
    except Exception as e:
        print(f"Error in determine_publisher_from_ids: {str(e)}")
        return []


def determine_main_publisher_from_source(source: dict) -> str:
    """
    Returns the cleaned/standardized publisher name for a source, in lower case.
    """
    def strip_company_abbreviations(name: str) -> str:
        for abbr in COMPANY_ABBREVIATIONS:
            if abbr in name:
                name = name.replace(abbr, '').strip()
            if abbr.rstrip() in name:
                name = name.replace(abbr.rstrip(), '').strip()
            if abbr.lstrip() in name:
                name = name.replace(abbr.lstrip(), '').strip()
        return name

    if not source:
        return 'unknown'
    if str(source.get('host_organization')).startswith('https://openalex.org/I'):
        return 'unknown'
    found_names: list[str] = source.get('host_organization_lineage_names', [])
    if not isinstance(found_names, list):
        found_names = [found_names]
    if not found_names:
        return 'unknown'
    final_name = 'unknown'
    for name in found_names:
        name = strip_company_abbreviations(name.lower())
        for common_publisher_name in PUBLISHER_NAME_MAPPING:
            if common_publisher_name in name:
                final_name = PUBLISHER_NAME_MAPPING[common_publisher_name]
                return final_name if final_name else 'unknown'
    return final_name


def get_publisher_for_work(work: Work) -> str:
    """Retrieve a cleaned/standardized publisher name for a given work."""
    if work is None:
        return 'unknown'
    sources: list[dict] = []
    for location in work.get('locations', []):
        if isinstance(location, dict):
            if location.get('source'):
                try:
                    sources.append(location.get('source', {}))
                except Exception as e:
                    print(f"Error in get_publisher_for_work: {str(e)}")
                    print(f"Location: {location}")
    if not sources:
        return 'unknown'
    publisher_names = set()
    for source in sources:
        publisher_names.add(determine_main_publisher_from_source(source))
    publisher_names.discard('unknown')
    publisher_names.discard('')
    publisher_names.discard(None)
    if len(publisher_names) > 1:
        print(f"Multiple publishers found for work: {work.get('id')}")
        print(f"Publishers: {publisher_names}")
        print(f'Returning the first one: {list(publisher_names)[0]}')
        return list(publisher_names)[0]
    if len(publisher_names) == 1:
        return list(publisher_names)[0]
    else:
        return 'unknown'


def analyze_publishers(works: list[dict], apply_limit: bool = True):
    """
    Analyze publisher data from works for open access Article Processing Charge (APC) fees only.
    Returns lists of publishers, their corresponding APC costs, overall total cost,
    count of for-profit publishers, publication titles, OA status flags, and DOIs.
    If apply_limit is True, only the most recent MAX_NUM works are analyzed.
    """
    publishers = []
    costs = []
    titles = []
    is_oa = []
    dois = []
    total_cost = 0
    for_profit_count = 0
    with st.spinner('Analyzing publications...'):
        works = sorted(works, key=lambda x: x.get('publication_date', '1900-01-01'), reverse=True)
        if apply_limit and len(works) > MAX_NUM:
            works = works[:MAX_NUM]
        publications = []
        for work in works:
            no_apc = False
            if not work.get('open_access', {}).get('is_oa', False):
                no_apc = True
            oa_status = work.get('open_access', {}).get('oa_status', '')
            if oa_status not in ['gold', 'hybrid', 'bronze', 'diamond']:
                no_apc = True
            publisher = get_publisher_for_work(work)
            if publisher is not None and publisher != 'unknown' and publisher not in PREPRINT_SERVERS:
                publications.append((work, publisher, no_apc))
        for work, publisher, no_apc in publications:
            apc_cost = 0
            if work.get('apc_paid') and isinstance(work['apc_paid'], dict):
                apc_cost = work['apc_paid'].get('value', 0)
            if not apc_cost and not no_apc:
                apc_cost = ESTIMATED_APC.get(publisher, ESTIMATED_APC['default'])
            publishers.append(publisher)
            costs.append(apc_cost)
            titles.append(work.get('title', 'Unknown Title'))
            is_oa.append(True if (apc_cost > 0) or not no_apc else False)
            dois.append(work.get('doi', 'N/A'))
            total_cost += apc_cost
            if publisher.lower() in FOR_PROFIT_PUBLISHERS and apc_cost > 0:
                for_profit_count += 1
    return publishers, costs, total_cost, for_profit_count, titles, is_oa, dois


def create_visualization(publisher_costs, return_fig=True):
    """Create a bar chart of publisher APC expenditure with for-profit publishers highlighted."""
    fig, ax = plt.subplots(figsize=(10, 3))
    top_publishers = dict(sorted(publisher_costs.items(), key=lambda x: x[1], reverse=True)[:10])
    colors = ['#ff6b6b' if p.lower() in FOR_PROFIT_PUBLISHERS else '#4a90e2' for p in top_publishers.keys()]
    bars = ax.bar(range(len(top_publishers)), list(top_publishers.values()), color=colors)
    ax.set_xticks(range(len(top_publishers)))
    ax.set_xticklabels(list(top_publishers.keys()), rotation=45, ha='right', fontsize=9)
    plt.subplots_adjust(bottom=0.18, left=0.08, right=0.98, top=0.98)
    ax.set_ylabel('$ Spent on APC fees', fontsize=9, labelpad=8)
    ax.set_xlabel('Publisher', fontsize=9, labelpad=8)
    ax.set_ylim(bottom=0)
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    ax.tick_params(axis='both', which='major', labelsize=8)
    # Format y-axis with commas and a dollar sign
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter('${x:,.0f}'))
    if return_fig:
        return fig
    else:
        plt.savefig('publisher_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        return 'publisher_distribution.png'


def display_analysis_results(author: Author):
    """Display analysis results for an author."""
    if not author:
        st.error("Could not fetch author details.")
        return
    st.subheader(f"Results for {author.get('display_name', 'Unknown')}")
    publications_data = fetch_publications(author)
    if not publications_data:
        st.error("No publications found for this author.")
        return
    # For authors, we remove the MAX_NUM limit so all publications are analyzed.
    publishers, costs, total_cost, for_profit_count, titles, is_oa, dois = analyze_publishers(publications_data, apply_limit=False)
    total_pubs = len(publishers)
    for_profit_percentage = (for_profit_count / total_pubs * 100) if total_pubs > 0 else 0
    publisher_costs = {}
    for pub, cost in zip(publishers, costs):
        publisher_costs[pub] = publisher_costs.get(pub, 0) + cost
    st.metric("Total Publications", total_pubs)
    st.metric("For-Profit Publications", f"{for_profit_count} ({for_profit_percentage:.1f}%)")
    st.metric("Total APC (Article Processing Charge) Cost", f"${total_cost:,.2f}")
    if publisher_costs:
        fig = create_visualization(publisher_costs)
        st.pyplot(fig, use_container_width=True)
        # Add a download button for the figure
        png_path = create_visualization(publisher_costs, return_fig=False)
        with open(png_path, "rb") as file:
            st.download_button(
                label="Download Figure as PNG",
                data=file,
                file_name="publisher_distribution.png",
                mime="image/png"
            )
    st.dataframe(pd.DataFrame({
        'Title': titles,
        'Publisher': publishers,
        'DOI': dois,
        'Estimated APC Cost': costs,
        'Is OA?': is_oa
    }))
    st.markdown("""
        <div style='font-size: 0.8rem; color: #666; border-top: 1px solid #ddd; padding-top: 1rem;'>
        Analysis for open access Article Processing Charge (APC) fees only. Calculated using costs from openalex.org.
        <br>
        Articles with unknown publishers, other publication types, and preprints are excluded.
        <br>
        Costs obtained from OpenAlex – where not available, estimated to be $1,500.
        <br>
        Feedback (<a href="mailto:david.bann@ucl.ac.uk">david.bann@ucl.ac.uk</a>) is welcome.
        <br>
        <a href="https://openalex.org/" target="_blank">OpenAlex API</a>
        &nbsp;&bull;&nbsp;
        <a href="https://github.com/dbann/pubanalyser" target="_blank">View on GitHub</a>
        </div>
    """, unsafe_allow_html=True)


def search_institutions(query: str) -> list:
    """Search for institutions using OpenAlex API."""
    try:
        oa_query = Institutions().search(query)
        institutions = []
        for record in chain(*oa_query.paginate(per_page=200)):
            institutions.append(record)
        return institutions
    except Exception as e:
        print(f"Error in search_institutions: {str(e)}")
        return []


def fetch_publications_institution(institution: dict) -> list:
    """
    Fetch institution publications (2024 only), stopping at MAX_NUM records.
    """
    with st.spinner('Fetching institution publications (2024 only)...'):
        try:
            inst_id = institution.get('id')
            if inst_id.startswith('https://openalex.org/'):
                inst_id = inst_id.split('/')[-1]
            query = Works().filter(institutions={"id": inst_id}, publication_year=2024)
            results = []
            for i, record in enumerate(chain(*query.paginate(per_page=200))):
                results.append(record)
                if i >= MAX_NUM - 1:
                    break
            return results
        except Exception as e:
            print(f"Error in fetch_publications_institution: {str(e)}")
            return []


def display_institution_analysis(institution: dict):
    """Display analysis results for an institution."""
    if not institution:
        st.error("Could not fetch institution details.")
        return
    st.subheader(f"Results for {institution.get('display_name', 'Unknown')}")
    publications_data = fetch_publications_institution(institution)
    if not publications_data:
        st.error("No publications found for this institution.")
        return
    publishers, costs, total_cost, for_profit_count, titles, is_oa, dois = analyze_publishers(publications_data)
    total_pubs = len(publishers)
    for_profit_percentage = (for_profit_count / total_pubs * 100) if total_pubs > 0 else 0
    publisher_costs = {}
    for pub, cost in zip(publishers, costs):
        publisher_costs[pub] = publisher_costs.get(pub, 0) + cost
    st.metric("Total Publications", total_pubs)
    st.metric("For-Profit Publications", f"{for_profit_count} ({for_profit_percentage:.1f}%)")
    st.metric("Total APC (Article Processing Charge) Cost", f"${total_cost:,.2f}")
    if publisher_costs:
        fig = create_visualization(publisher_costs)
        st.pyplot(fig, use_container_width=True)
        # Add a download button for the figure
        png_path = create_visualization(publisher_costs, return_fig=False)
        with open(png_path, "rb") as file:
            st.download_button(
                label="Download Figure as PNG",
                data=file,
                file_name="publisher_distribution.png",
                mime="image/png"
            )
    st.dataframe(pd.DataFrame({
        'Title': titles,
        'Publisher': publishers,
        'DOI': dois,
        'Estimated APC Cost': costs,
        'Is OA?': is_oa
    }))
    st.markdown("""
        <div style='font-size: 0.8rem; color: #666; border-top: 1px solid #ddd; padding-top: 1rem;'>
        Analysis for open access Article Processing Charge (APC) fees only. Calculated using costs from openalex.org.
        <br>
        Articles with unknown publishers, other publication types, and preprints are excluded.
        <br>
        Costs obtained from OpenAlex – where not available, estimated to be $1,500.
        <br>
        Feedback (<a href="mailto:david.bann@ucl.ac.uk">david.bann@ucl.ac.uk</a>) is welcome.
        <br>
        <a href="https://openalex.org/" target="_blank">OpenAlex API</a>
        &nbsp;&bull;&nbsp;
        <a href="https://github.com/dbann/pubanalyser" target="_blank">View on GitHub</a>
        </div>
    """, unsafe_allow_html=True)


def main():
    st.title("Publication Cost Tracker")
    st.write("Discover the hidden costs behind publishing your research. Simply search for an author or an institution to receive a detailed breakdown of publication expenses.")
    # Two main tabs for Author and Institution analysis.
    author_tab, institution_tab = st.tabs(["Author Analysis", "Institution Analysis"])
    with author_tab:
        # Two sub-tabs for searching by Name or ID.
        by_name, by_id = st.tabs(["By Name", "By ID"])
        with by_name:
            query = st.text_input("Enter an author name", placeholder="e.g., John Smith")
            if query:
                authors = search_authors(query)
                if authors:
                    for author in authors:
                        inst = "Unknown"
                        last_institutions = author.get('last_known_institutions', [])
                        if isinstance(last_institutions, list) and last_institutions:
                            inst = last_institutions[0].get('display_name', "Unknown")
                        if st.button(f"{author.get('display_name')} ({inst})", key=clean_author_id(author.get('id'))):
                            st.session_state.author_details = author
                            st.session_state.author_id = clean_author_id(author.get('id'))
        with by_id:
            query = st.text_input("Enter an author ID (ORCID or OpenAlex)", placeholder="e.g., A5008020290")
            if st.button("Search by ID"):
                author_info, author_id = get_author_by_id(query)
                if author_id:
                    st.session_state.author_details = author_info
                    st.session_state.author_id = author_id
                else:
                    st.error("Invalid author ID.")
        if st.session_state.get("author_details"):
            display_analysis_results(st.session_state.author_details)
    with institution_tab:
        query = st.text_input("Enter an institution name", placeholder="e.g., University of Oxford")
        if query:
            inst_results = search_institutions(query)
            if inst_results:
                for inst in inst_results:
                    if st.button(inst.get('display_name', 'Unknown'), key=inst.get('id')):
                        st.session_state.institution = inst
            else:
                st.error("No institutions found.")
        if st.session_state.get("institution"):
            display_institution_analysis(st.session_state.institution)


if __name__ == "__main__":
    main()
