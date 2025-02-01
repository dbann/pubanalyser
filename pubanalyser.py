import streamlit as st
import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt
import pyalex
from pyalex import Author, Authors, Work, Works, Publisher, Publishers
from rich import print
from itertools import chain
from streamlit.logger import get_logger
from constants import USER_EMAIL, FOR_PROFIT_PUBLISHERS, PREPRINT_SERVERS, ESTIMATED_APC, PUBLISHER_NAME_MAPPING, COMPANY_ABBREVIATIONS, MAX_NUM

_LOGGER = get_logger(__name__)


# setup pyalex

pyalex.config.email = USER_EMAIL
pyalex.config.max_retries = 5
pyalex.config.retry_backoff_factor = 0.2
pyalex.config.retry_http_codes = [429, 500, 503]





def get_author_by_id(identifier:str) -> tuple[Author, str|None]:
    """Get author details for an ORCID or OpenAlex author ID via OpenAlex API."""
    try:
        author:Author =  Authors()[identifier]
        return author, clean_author_id(author.get('id',None))
    except Exception as e:
        print(f"Error in get_author_by_id: {str(e)}")
        return {}, None

def search_authors(query: str) -> list[Author|None]:
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

def clean_author_id(author_id: str) -> str|None:
    """Clean and format the author ID."""
    if not author_id or not isinstance(author_id, str):
        return None
    if '/' in author_id:
        author_id = author_id.split('/')[-1]
    author_id = author_id.lstrip('Aa')
    return f"A{author_id}"


def fetch_publications(author: Author) -> list[Work|None]:
    """Fetch publications data for an author_id from OpenAlex API."""
    with st.spinner('Fetching publication data...'):
        try:
            query = Works().filter(author={"id":author.get('id')})
            results = []
            for record in chain(*query.paginate(per_page=200)):
                results.append(record)
            return results

        except Exception as e:
            print(f"Error in fetch_publications: {str(e)}")
            return []
def get_publishers_by_ids(publisher_ids: set[str]) -> list[Publisher|None]:
    if len(publisher_ids) == 0:
        return []
    try:
        return [Publishers()[publisher_id] for publisher_id in publisher_ids]
    except Exception as e:
        print(f"Error in determine_publisher_from_ids: {str(e)}")
        return []

def determine_main_publisher_from_source(source:dict) -> str:
    """
    Returns the cleaned/standardized publisher name for a source, in lower case.
    """
    def strip_company_abbreviations(name:str) -> str:
        for abbr in COMPANY_ABBREVIATIONS:
            if abbr in name:
                name = name.replace(abbr,'').strip()
            if abbr.rstrip() in name:
                name = name.replace(abbr.rstrip(),'').strip()
            if abbr.lstrip() in name:
                name = name.replace(abbr.lstrip(),'').strip()
        return name

    if not source:
        return 'unknown'

    if str(source.get('host_organization')).startswith('https://openalex.org/I'):
        return 'unknown'
    found_names: list[str] = source.get('host_organization_lineage_names',[])
    if not isinstance(found_names, list):
        found_names = [found_names]
    if not found_names:
        return 'unknown'
    final_name = 'unknown'
    for name in found_names:
        name = strip_company_abbreviations(name.lower())
        for common_publisher_name in PUBLISHER_NAME_MAPPING:
            if common_publisher_name in name:
                final_name =  PUBLISHER_NAME_MAPPING[common_publisher_name]
                return final_name if final_name else 'unknown'


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


def analyze_publishers(works: list[dict]):
    """Analyze publisher data from works."""
    publishers = []
    costs = []
    titles = []
    is_oa = []
    total_cost = 0
    for_profit_count = 0
    text = 'Analyzing newest publications...'
    # sort works by publication_date and limit to max_num
    works = sorted(works, key=lambda x: x.get('publication_date', '1900-01-01'), reverse=True)
    if len(works) > MAX_NUM:
        works = works[:MAX_NUM]

    with st.spinner(text):
        # Get publisher info for each work and filter out None, unknown publishers, and preprints
        publications = []
        for work in works:
            no_apc = False
            if not work.get('open_access',{}).get('is_oa',False):
                no_apc = True
            oa_color = work.get('open_access',{}).get('oa_status','')
            if oa_color not in ['gold', 'hybrid', 'bronze', 'diamond']:
                no_apc = True

            publisher = get_publisher_for_work(work)
            if publisher is not None and publisher != 'unknown' and publisher not in PREPRINT_SERVERS:
                publications.append((work, publisher, no_apc))

        for work, publisher, no_apc in publications:
            # Check for OpenAlex's estimated APC first
            apc_cost = 0
            if work.get('apc_paid') and isinstance(work['apc_paid'], dict):
                apc_cost = work['apc_paid'].get('value')

            # If no OpenAlex APC, use our estimates
            if not apc_cost and not no_apc:
                apc_cost = ESTIMATED_APC.get(publisher, ESTIMATED_APC['default'])

            publishers.append(publisher)
            costs.append(apc_cost)
            titles.append(work.get('title', 'Unknown Title'))
            is_oa.append(True if (apc_cost > 0) or not no_apc else False)
            total_cost += apc_cost

            if publisher in FOR_PROFIT_PUBLISHERS and apc_cost > 0:
                for_profit_count += 1


    return publishers, costs, total_cost, for_profit_count, titles, is_oa

def create_visualization(publishers_count, return_fig=True):
    """Create a bar chart of publisher distribution with for-profit publishers highlighted."""
    fig, ax = plt.subplots(figsize=(10, 3))  # Further reduced height

    top_publishers = dict(sorted(publishers_count.items(), key=lambda x: x[1], reverse=True)[:10])

    colors = ['#ff6b6b' if p.lower() in FOR_PROFIT_PUBLISHERS else '#4a90e2'
              for p in top_publishers.keys()]

    bars = plt.bar(range(len(top_publishers)), list(top_publishers.values()), color=colors)

    plt.xticks(range(len(top_publishers)),
              list(top_publishers.keys()),
              rotation=45,
              ha='right',
              fontsize=9)

    plt.subplots_adjust(bottom=0.18, left=0.08, right=0.98, top=0.98)
    plt.ylabel('Number of Publications', fontsize=9, labelpad=8)
    plt.xlabel('Publisher', fontsize=9, labelpad=8)
    plt.ylim(bottom=0)
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    ax.tick_params(axis='both', which='major', labelsize=8)

    if return_fig:
        return fig
    else:
        plt.savefig('publisher_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        return 'publisher_distribution.png'

def display_analysis_results(author: Author):
    """Display the analysis results for a given author ID."""
    # Fetch author details first
    if not author:
        st.error("Could not fetch author details.")
        return

    # Display author information in a more compact way with consistent styling
    st.markdown("""
        <h3 style='margin-bottom: 0.5rem;'>Author Information</h3>
        """, unsafe_allow_html=True)

    # Author info in columns with aligned text
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"<div style='font-size: 1.1rem;'><strong>Name:</strong> {author.get('display_name', 'Unknown')}</div>",
            unsafe_allow_html=True
        )
    with col2:
        institutions = author.get('last_known_institutions', [])
        current_affiliation = institutions[0].get('display_name', 'Unknown affiliation') if institutions else 'Unknown affiliation'
        st.markdown(
            f"<div style='font-size: 1.1rem;'><strong>Current Affiliation:</strong> {current_affiliation}</div>",
            unsafe_allow_html=True
        )

    st.markdown("<hr style='margin: 0.5rem 0;'>", unsafe_allow_html=True)

    # Fetch publications
    publications_data = fetch_publications(author)

    if not publications_data:
        st.error("No publications found for this author.")
        return

    # Analyze publishers
    publishers, costs, total_cost, for_profit_count, titles, is_oa = analyze_publishers(publications_data)
    total_pubs = len(publishers)
    for_profit_percentage = (for_profit_count / total_pubs * 100) if total_pubs > 0 else 0
    publishers_count = Counter(publishers)

    # Display results header
    st.markdown("<h3 style='margin-top: 1rem; margin-bottom: 0.5rem;'>Publication Analysis Results</h3>", unsafe_allow_html=True)

    # Summary statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Publications", total_pubs)
    with col2:
        st.metric("For-Profit Publications", f"{for_profit_count} ({for_profit_percentage:.1f}%)")
    with col3:
        st.metric("Estimated Total Cost", f"${total_cost:,.2f}")

    # Display visualization and export options
    if publishers_count:
        st.markdown("<h4 style='margin-top: 1rem; margin-bottom: 0.5rem;'>Publisher Distribution</h4>", unsafe_allow_html=True)

        # Display the plot
        fig = create_visualization(publishers_count)
        st.pyplot(fig, use_container_width=True)
        plt.close()

        # Create export buttons in columns
        st.markdown("<h4 style='margin-top: 1rem; margin-bottom: 0.5rem;'>Export Options</h4>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)

        with col1:
            # Export visualization as PNG
            if st.button("Export Graph as PNG"):
                # Create and save the visualization
                png_path = create_visualization(publishers_count, return_fig=False)

                # Read the saved file and create a download button
                with open(png_path, "rb") as file:
                    btn = st.download_button(
                        label="Download PNG",
                        data=file,
                        file_name="publisher_distribution.png",
                        mime="image/png"
                    )

        with col2:
            # Export detailed data as CSV
            csv_data = pd.DataFrame({
                'Metric': ['Author', 'Affiliation'] + ['Total Publications', 'For-Profit Publications', 'For-Profit Percentage', 'Total Estimated Cost'],
                'Value': [
                    author.get('display_name', 'Unknown'),
                    current_affiliation,
                    str(total_pubs),
                    str(for_profit_count),
                    f"{for_profit_percentage:.1f}%",
                    f"${total_cost:,.2f}"
                ]
            })

            # Add detailed publisher breakdown
            detailed_df = pd.DataFrame({
                'Title': titles,
                'Publisher': publishers,
                "is OA": is_oa,
                'Estimated Cost': costs,
                'For Profit': [p.lower() in FOR_PROFIT_PUBLISHERS for p in publishers]
            })

            # Convert to CSV
            csv = pd.concat([csv_data, pd.DataFrame({'Metric': [''], 'Value': ['']}),
                           detailed_df.reset_index(drop=True)]).to_csv(index=False)

            st.download_button(
                label="Export Full Results as CSV",
                data=csv,
                file_name="publication_analysis.csv",
                mime="text/csv"
            )

    # Display detailed breakdown (only once, at the end)
    st.markdown("<h4 style='margin-top: 1rem; margin-bottom: 0.5rem;'>Detailed Cost Breakdown</h4>", unsafe_allow_html=True)
    breakdown_df = pd.DataFrame({
        'Title': titles,
        'Is OA?': is_oa,
        'Publisher': publishers,
        'Estimated Cost': costs
    })
    st.dataframe(breakdown_df)

    # Add footnote at the bottom
    st.markdown("<br>", unsafe_allow_html=True)  # Add some space
    st.markdown("""
        <div style='font-size: 0.8rem; color: #666; border-top: 1px solid #ddd; padding-top: 1rem;'>
        Past 100 research articles with known publishers analysed using OpenAlex database
        (<a href="https://openalex.org/" target="_blank">https://openalex.org/</a>).
        Articles with unknown publishers, other publication types, and preprints are excluded.
        Costs obtained from OpenAlex - where not available estimated to be $1,500.
        This is a proof of concept prototype.
        Feedback (<a href="mailto:david.bann@ucl.ac.uk">david.bann@ucl.ac.uk</a>) is welcome.
        </div>
    """, unsafe_allow_html=True)

def main():

    # Title in sidebar
    st.sidebar.title("Publication Cost Tracker")

    with st.sidebar:
        st.header("Find Author Publications")

        # Add tabs for different search methods
        search_tab,  id_tab = st.tabs(["Search by Name", "Search by (ORC)ID"])

        with search_tab:
            author_query = st.text_input("Search by Name", placeholder="e.g., John Smith")
            if author_query:
                authors = search_authors(author_query)
                if authors:
                    st.write("Select an author:")
                    for author in authors:
                        # Create a button for each author
                        institute = "Unknown"
                        last_instutions = author.get('last_known_institutions', None)
                        if isinstance(last_instutions, list) and last_instutions:
                            institute = last_instutions[0].get('display_name')
                        button_label = f"{author.get('display_name')}\n{institute}\n({author.get('works_count')} works)"
                        if st.button(button_label, key=clean_author_id(author.get('id'))):
                            st.session_state.author_id = clean_author_id(author.get('id'))
                            st.session_state.author_details = author
                            st.session_state.analyze_clicked = True
                else:
                    st.error("No authors found.")


        with id_tab:
            input_id = st.text_input("OpenAlex Author ID or ORCID", placeholder="e.g., A5008020290, https://openalex.org/authors/A5008020290, https://orcid.org/0000-0002-1825-0097, 0000-0002-1825-0097")
            if st.button("Analyze Using ID"):
                author_info, author_id = get_author_by_id(input_id)
                if author_id:
                    st.session_state.author_details = author_info
                    st.session_state.analyze_clicked = True
                else:
                    st.error("Invalid author ID.")

    # Main content area - Display analysis results
    if 'analyze_clicked' in st.session_state and 'author_id' in st.session_state:
        display_analysis_results(st.session_state.author_details)

if __name__ == "__main__":
    main()
