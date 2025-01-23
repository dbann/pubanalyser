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
                total_cost += apc_cost
                
                if publisher in FOR_PROFIT_PUBLISHERS:
                    for_profit_count += 1
                    
        except Exception as e:
            print(f"Error in analyze_publishers: {str(e)}")
    
    return publishers, costs, total_cost, for_profit_count

def create_visualization(publishers_count):
    """Create a bar chart of publisher distribution with for-profit publishers highlighted."""
    fig, ax = plt.subplots(figsize=(10, 3))  # Further reduced height
    
    top_publishers = dict(sorted(publishers_count.items(), key=lambda x: x[1], reverse=True)[:10])
    
    colors = ['#ff6b6b' if p.lower() in FOR_PROFIT_PUBLISHERS else '#4a90e2' 
              for p in top_publishers.keys()]
    
    bars = plt.bar(range(len(top_publishers)), list(top_publishers.values()), color=colors)
    
    # Improve x-axis label formatting
    plt.xticks(range(len(top_publishers)), 
              list(top_publishers.keys()), 
              rotation=45,
              ha='right',
              fontsize=9)
    
    # Tighter layout with minimal margins
    plt.subplots_adjust(bottom=0.18, left=0.08, right=0.98, top=0.98)
    
    # Improve y-axis with smaller fonts
    plt.ylabel('Number of Publications', fontsize=9, labelpad=8)
    plt.xlabel('Publisher', fontsize=9, labelpad=8)
    
    # Ensure y-axis starts at 0
    plt.ylim(bottom=0)
    
    # Add gridlines for better readability
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    
    # Make tick labels more compact
    ax.tick_params(axis='both', which='major', labelsize=8)
    
    return fig
def main():
    st.set_page_config(page_title="Publication Cost Tracker", layout="wide")
    
    # Title in sidebar
    st.sidebar.title("Publication Cost Tracker")
    
    with st.sidebar:
        st.header("Enter Your Details")
        st.markdown("""
        Find your OpenAlex Author ID at [OpenAlex.org](https://openalex.org/)
        """)
        author_id = st.text_input("OpenAlex Author ID", value="A5070446713", placeholder="e.g., A5008020290")
        
        analyze_button = st.button("Analyze Publications")
    
    if analyze_button and author_id:
        with st.spinner("Analyzing your publications..."):
            clean_id = clean_author_id(author_id)
            
            data = fetch_publications(clean_id)
            # Filter out preprints and unknown publishers
            filtered_results = [r for r in data.get('results', []) 
                              if r is not None and 
                              get_publisher_info(r) not in PREPRINT_SERVERS and 
                              get_publisher_info(r) != 'unknown']
            
            if not filtered_results:
                st.info("No publications with known publishers found. Please check your Author ID and try again.")
                return
                
            # Get author details from OpenAlex
            author_details = fetch_author_details(clean_id)
            author_name = "Unknown Author"
            affiliation = "Unknown Affiliation"
            
            if author_details:
                author_name = author_details.get('display_name', "Unknown Author")
                last_known_institutions = author_details.get('last_known_institutions', [])
                if last_known_institutions and isinstance(last_known_institutions, list) and len(last_known_institutions) > 0:
                    primary_inst = last_known_institutions[0]
                    if isinstance(primary_inst, dict) and 'display_name' in primary_inst:
                        affiliation = primary_inst['display_name']

            st.title("Publication output")
            st.subheader(f"Author: {author_name} ({affiliation})")
            
            total_works = len(filtered_results)
            publishers, costs, total_cost, for_profit_count = analyze_publishers(filtered_results)
            publishers_count = Counter(publishers)
            
            for_profit_percentage = (for_profit_count / total_works * 100) if total_works > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Analysis of publications with known publishers", 
                         f"{total_works} of {len(data['results'])} total")
            with col2:
                st.metric("For-Profit Publishers", 
                         f"{for_profit_count} ({for_profit_percentage:.1f}%)")
            with col3:
                st.metric("Total Estimated Publisher Costs", 
                         f"${total_cost:,.2f}")
            
            if publishers:  # Only create visualization if there are publishers to show
                fig = create_visualization(publishers_count)
                st.pyplot(fig)
            
            st.subheader("Publication Details")
            if publishers:  # Only create dataframe if there are publishers to show
                publisher_df = pd.DataFrame({
                    'Publisher': [p.title() for p in publishers],
                    'Est. APC': [f"${c:,}" for c in costs]
                })
                st.dataframe(publisher_df)
                
                csv = publisher_df.to_csv(index=False)
                st.download_button(
                    "Download Results CSV",
                    csv,
                    "publisher_analysis.csv",
                    "text/csv",
                    key='download-csv'
                )
            
            st.markdown("""
            ---
            Past 100 research articles with known publishers analysed using OpenAlex database ([https://openalex.org/](https://openalex.org/)). Articles with unknown publishers, other publication types, and preprints are excluded.  
            Costs obtained from OpenAlex - where not available estimated to be $1,500.  
            This is a proof of concept prototype. Feedback (david.bann@ucl.ac.uk) is appreciated.
            """)
            
if __name__ == "__main__":
    main()
