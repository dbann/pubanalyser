


import streamlit as st
import requests
import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt

# Configuration
FOR_PROFIT_PUBLISHERS = {
    'elsevier', 'springer', 'springer nature', 'wiley', 'taylor & francis',
    'sage publications', 'frontiers media sa', 'ieee', 'emerald', 'karger',
    'thieme', 'wolters kluwer', 'acs publications', 'lippincott',
    'lippincott williams & wilkins', 'wolters kluwer health',
    'nature publishing group', 'nature portfolio', 'biomed central',
    'biomedcentral', 'bmc', 'hindawi', 'mdpi', 'informa', 'f1000', 'relx',
    'relx group', 'bentham science', 'inderscience', 'igi global', 'sciencedirect',
    'de gruyter', 'sciendo', 'omics international', 'rsc publishing',
}

PREPRINT_SERVERS = {
    'cold spring harbor laboratory',
    'biorxiv',
    'medrxiv',
    'arxiv',
    'ssrn'
}

ESTIMATED_APC = {
    'elsevier': 3000,
    'springer nature': 2800,
    'wiley': 2500,
    'taylor & francis': 2400,
    'sage publications': 2000,
    'frontiers media sa': 2950,
    'ieee': 2000,
    'emerald': 2800,
    'karger': 2800,
    'thieme': 2500,
    'wolters kluwer': 2500,
    'biomed central': 2000,
    'plos': 1700,
    'default': 1500
}

def search_by_orcid(orcid):
    """Search for author using ORCID ID via OpenAlex API."""
    try:
        base_url = "https://api.openalex.org/authors"
        params = {
            'filter': f"orcid:{orcid}",
            'mailto': 'david.bann@ucl.ac.uk'
        }

        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get('results') and len(data['results']) > 0:
            author = data['results'][0]
            return {
                'id': author['id'].split('/')[-1],
                'name': author.get('display_name', 'Unknown'),
                'affiliation': author.get('last_known_institutions', [{}])[0].get('display_name', 'Unknown affiliation'),
                'works_count': author.get('works_count', 0),
                'orcid': orcid
            }
        return None
    except Exception as e:
        print(f"Error in search_by_orcid: {str(e)}")
        return None

def search_authors(query):
    """Search for authors using OpenAlex API."""
    try:
        base_url = "https://api.openalex.org/authors"
        params = {
            'search': query,
            'per-page': 10,  # Limit to top 10 results
            'mailto': 'david.bann@ucl.ac.uk'
        }

        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        authors = []
        if 'results' in data:
            for author in data['results']:
                author_info = {
                    'id': author['id'].split('/')[-1],
                    'name': author.get('display_name', 'Unknown'),
                    'affiliation': 'Unknown affiliation',
                    'works_count': author.get('works_count', 0)
                }

                # Get latest affiliation
                if author.get('last_known_institutions'):
                    if len(author['last_known_institutions']) > 0:
                        author_info['affiliation'] = author['last_known_institutions'][0].get('display_name', 'Unknown affiliation')

                authors.append(author_info)

        return authors
    except Exception as e:
        print(f"Error in search_authors: {str(e)}")
        return []

def clean_author_id(author_id):
    """Clean and format the author ID."""
    if 'openalex.org' in author_id:
        author_id = author_id.split('/')[-1]
    # Remove any existing 'A' or 'a' prefix and add uppercase 'A'
    author_id = author_id.lstrip('Aa')
    return f"A{author_id}"

def fetch_author_details(author_id):
    """Fetch author details including current affiliation from OpenAlex API."""
    try:
        url = f"https://api.openalex.org/authors/{author_id}"
        params = {'mailto': 'david.bann@ucl.ac.uk'}

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except:
        return None

def fetch_publications(author_id):
    """Fetch publications data from OpenAlex API."""
    with st.spinner('Fetching publication data (limited to last 100 articles)...'):
        try:
            base_url = "https://api.openalex.org/works"
            params = {
                'filter': f"author.id:{author_id},type:article",
                'per-page': 100,
                'sort': 'publication_date:desc',
                'mailto': 'david.bann@ucl.ac.uk'
            }

            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            if 'results' in data and isinstance(data['results'], list):
                return data
            return {'results': []}

        except:
            return {'results': []}

def get_publisher_info(work):
    """Safely extract publisher information from a work."""
    if work is None:
        return 'unknown'

    try:
        # Debug: Print the relevant fields to see what we're getting
        print("\nDEBUG Publisher Info:")
        print("Direct publisher:", work.get('publisher'))
        print("Host org:", work.get('primary_location', {}).get('source', {}).get('host_organization_name'))
        print("Display name:", work.get('primary_location', {}).get('source', {}).get('display_name'))
        print("Source:", work.get('primary_location', {}).get('source', {}))

        publisher = None

        # Try multiple paths to get publisher info
        if isinstance(work, dict):
            # Try direct publisher field
            if work.get('publisher'):
                publisher = str(work['publisher']).lower()
            # Try host organization name
            elif work.get('primary_location', {}).get('source', {}).get('host_organization_name'):
                publisher = str(work['primary_location']['source']['host_organization_name']).lower()
            # Try display name from source
            elif work.get('primary_location', {}).get('source', {}).get('display_name'):
                publisher = str(work['primary_location']['source']['display_name']).lower()
            # Try other locations if primary fails
            elif work.get('locations'):
                for location in work['locations']:
                    if location.get('source', {}).get('host_organization_name'):
                        publisher = str(location['source']['host_organization_name']).lower()
                        break
                    elif location.get('source', {}).get('display_name'):
                        publisher = str(location['source']['display_name']).lower()
                        break

        if not publisher:
            print("No publisher found in any field")
            return 'unknown'

        print(f"Found raw publisher: {publisher}")

        # Clean up common variations
        publisher = publisher.replace('ltd', '').replace('limited', '').strip()

        # Extended publisher mapping
        if any(p in publisher for p in ['elsevier', 'sciencedirect', 'cell press', 'relx group']):
            return 'elsevier'
        elif any(p in publisher for p in ['springer', 'nature portfolio', 'nature publishing']):
            return 'springer nature'
        elif any(p in publisher for p in ['wiley', 'blackwell']):
            return 'wiley'
        elif any(p in publisher for p in ['taylor & francis', 'taylor and francis', 'routledge']):
            return 'taylor & francis'
        elif any(p in publisher for p in ['wolters', 'lippincott']):
            return 'wolters kluwer'
        elif any(p in publisher for p in ['biomed central', 'bmc', 'biomedcentral']):
            return 'biomed central'
        elif 'sage' in publisher:
            return 'sage publications'
        elif 'frontiers' in publisher:
            return 'frontiers media sa'
        elif 'ieee' in publisher:
            return 'ieee'
        elif 'karger' in publisher:
            return 'karger'
        elif 'thieme' in publisher:
            return 'thieme'
        elif 'hindawi' in publisher:
            return 'hindawi'
        elif 'mdpi' in publisher:
            return 'mdpi'
        elif 'plos' in publisher or 'public library of science' in publisher:
            return 'plos'
        elif 'oxford university press' in publisher:
            return 'oxford university press'
        elif 'cambridge university press' in publisher:
            return 'cambridge university press'

        return publisher

    except Exception as e:
        print(f"Error in get_publisher_info: {str(e)}")
        return 'unknown'

def analyze_publishers(works):
    """Analyze publisher data from works."""
    publishers = []
    costs = []
    titles = []  # Add this line
    total_cost = 0
    for_profit_count = 0

    with st.spinner('Analyzing publications...'):
        try:
            # Get publisher info for each work and filter out None, unknown publishers, and preprints
            publications = []
            for work in works:
                publisher = get_publisher_info(work)
                if publisher is not None and publisher != 'unknown' and publisher not in PREPRINT_SERVERS:
                    publications.append((work, publisher))

            for work, publisher in publications:
                # Check for OpenAlex's estimated APC first
                apc_cost = None
                if work.get('apc_paid') and isinstance(work['apc_paid'], dict):
                    apc_cost = work['apc_paid'].get('value')

                # If no OpenAlex APC, use our estimates
                if not apc_cost:
                    apc_cost = ESTIMATED_APC.get(publisher, ESTIMATED_APC['default'])

                publishers.append(publisher)
                costs.append(apc_cost)
                titles.append(work.get('title', 'Unknown Title'))  # Add this line
                total_cost += apc_cost

                if publisher in FOR_PROFIT_PUBLISHERS:
                    for_profit_count += 1

        except Exception as e:
            print(f"Error in analyze_publishers: {str(e)}")

    return publishers, costs, total_cost, for_profit_count, titles  # Add titles to return

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

def display_analysis_results(author_id):
    """Display the analysis results for a given author ID."""
    # Fetch author details first
    author_details = fetch_author_details(author_id)
    if not author_details:
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
            f"<div style='font-size: 1.1rem;'><strong>Name:</strong> {author_details.get('display_name', 'Unknown')}</div>",
            unsafe_allow_html=True
        )
    with col2:
        institutions = author_details.get('last_known_institutions', [])
        current_affiliation = institutions[0].get('display_name', 'Unknown affiliation') if institutions else 'Unknown affiliation'
        st.markdown(
            f"<div style='font-size: 1.1rem;'><strong>Current Affiliation:</strong> {current_affiliation}</div>",
            unsafe_allow_html=True
        )

    st.markdown("<hr style='margin: 0.5rem 0;'>", unsafe_allow_html=True)

    # Fetch publications
    publications_data = fetch_publications(author_id)

    if not publications_data.get('results'):
        st.error("No publications found for this author.")
        return

    # Analyze publishers
    publishers, costs, total_cost, for_profit_count, titles = analyze_publishers(publications_data['results'])
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
                    author_details.get('display_name', 'Unknown'),
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
    st.set_page_config(page_title="Publication Cost Tracker", layout="wide")

    # Title in sidebar
    st.sidebar.title("Publication Cost Tracker")

    with st.sidebar:
        st.header("Find Your Publications")

        # Add tabs for different search methods
        search_tab, orcid_tab, id_tab = st.tabs(["Search by Name", "Use ORCID", "Use OpenAlex ID"])

        with search_tab:
            author_query = st.text_input("Search by Name", placeholder="e.g., John Smith")
            if author_query:
                authors = search_authors(author_query)
                if authors:
                    st.write("Select your profile:")
                    for author in authors:
                        # Create a button for each author
                        button_label = f"{author['name']}\n{author['affiliation']}\n({author['works_count']} works)"
                        if st.button(button_label, key=author['id']):
                            st.session_state.author_id = author['id']
                            st.session_state.analyze_clicked = True
                else:
                    st.info("No authors found. Try refining your search.")

        with orcid_tab:
            orcid = st.text_input("ORCID ID", placeholder="e.g., 0000-0002-1825-0097")
            if st.button("Search ORCID"):
                if orcid:
                    author_info = search_by_orcid(orcid)
                    if author_info:
                        st.session_state.author_id = author_info['id']
                        st.session_state.analyze_clicked = True
                    else:
                        st.error("No author found with this ORCID ID")

        with id_tab:
            openalex_id = st.text_input("OpenAlex Author ID", placeholder="e.g., A5008020290")
            if st.button("Analyze Using ID"):
                if openalex_id:
                    clean_id = clean_author_id(openalex_id)
                    st.session_state.author_id = clean_id
                    st.session_state.analyze_clicked = True

    # Main content area - Display analysis results
    if 'analyze_clicked' in st.session_state and 'author_id' in st.session_state:
        display_analysis_results(st.session_state.author_id)

if __name__ == "__main__":
    main()
