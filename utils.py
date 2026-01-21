import json
import sys
import time
from datetime import datetime
import pathlib
import re

from lxml import etree
from pure_parse import populate_workday_mapping, get_pure_author_id

PURE_NS = "v1.dataset.pure.atira.dk"
PURE = "{%s}" % PURE_NS

PURE_CMNS = "v3.commons.pure.atira.dk"
CMNS = "{%s}" % PURE_CMNS


# Organization IDs get populated with Pure API queries
WORKDAY_ORG_MAPPING = {}

# Publishers are hard-coded strings
PUBLISHER_MAPPING = {
    'ACOM': "ucarncar-publisher-acom",
    'CGD': "ucarncar-publisher-cgd",
    'CISL': "ucarncar-publisher-cisl",
    'RDA': "ucarncar-publisher-cisl-isd",  # Map to CISL-ISD
    'GDEX': "ucarncar-publisher-cisl-isd",  # Map to CISL-ISD
    'EOL': "ucarncar-publisher-eol",
    'HAO': "ucarncar-publisher-hao",
    'Library': "ucarncar-publisher-ncar-library",
    'RAL': "ucarncar-publisher-ral",
    'UCP': "ucarncar-publisher-ucp",
    'NCAR': "ucarncar-publisher-ncar",  # Always place at the end of this list
}


def get_organization_id(org_string):
    """
    Given a string representing an NCAR organization, find the first mapping entry with a partial match and
    return the associated UUID from Workday.   If there is no partial match, return None.

    The partial string match test is case-sensitive.
    """
    global WORKDAY_ORG_MAPPING
    if not WORKDAY_ORG_MAPPING:
        WORKDAY_ORG_MAPPING = populate_workday_mapping()
    workday_id = None
    for key, value in WORKDAY_ORG_MAPPING.items():
        if key in org_string:
            workday_id = value
            break
    return workday_id


def get_publisher_string(org_string):
    """
    Given a string representing an NCAR organization, find the first PUBLISHER_MAPPING entry with a partial match and
    return the associated UUID from Workday.   If there is no partial match, return None.

    The partial string match test is case-sensitive.
    """
    publisher_string = None
    for key, value in PUBLISHER_MAPPING.items():
        if key in org_string:
            publisher_string = value
            break
    return publisher_string


def print_stderr(msg):
    print(msg, file=sys.stderr)

def xml_init(use_namespaces):
    if use_namespaces:
        root_element = etree.Element(PURE + "datasets", nsmap={'v1': PURE_NS, 'v3': PURE_CMNS})
    else:
        root_element = etree.Element(PURE + "datasets", nsmap={None: PURE_NS, 'v3': PURE_CMNS})
    return root_element


def write_xml(root, xml_header=None, output_file=None):
    content = etree.tostring(root, pretty_print=True, encoding='unicode')
    if xml_header:
        content = xml_header + content
    if not output_file:
        sys.stdout.write(content)
    else:
        file = open(output_file, 'w')
        file.write(content)
        file.close()


def validate_xml(root):
    current_directory = pathlib.Path(__file__).parent.absolute().as_posix()
    schema_file = current_directory + '/PURE_XSD/dataset.xsd'
    xmlschema_doc = etree.parse(schema_file)
    xmlschema = etree.XMLSchema(xmlschema_doc)
    xmlschema.assertValid(root)


def fill_date_fields(element, date_parts):
    year = etree.SubElement(element, CMNS + 'year')
    year.text = date_parts[0]
    if len(date_parts) > 1:
        month = etree.SubElement(element, CMNS + 'month')
        month.text = date_parts[1]
    if len(date_parts) > 2:
        day = etree.SubElement(element, CMNS + 'day')
        day.text = date_parts[2]


def get_extras_value(pkg_dict, key):
    """ Return the value associated with the given key in the package extras list.
        If the given key is not in the list, return None.
    """
    return_value = None
    for extra in pkg_dict['extras']:
        if extra['key'] == key:
            return_value = extra['value']
    return return_value


def is_doi(url_string):
    """  Returns True if urlString appears to be a DOI.  Otherwise, it returns False.
    """
    return_value = False
    if url_string:
        if url_string.startswith('http://doi.org/') or url_string.startswith('https://doi.org/'):
            return_value = True
    return return_value


def get_doi_suffix(url_string):
    suffix = url_string.split('doi.org/', 1)[1]
    return suffix


def get_date_parts(iso_date):
    date = iso_date.split('T')[0]
    components = date.split('-')
    return components


def get_extent_parts(extent):
    """ Parse Solr date range with format similar to "[1992-11-01 TO 1993-02-28]"
        Sometimes the second value is '*', which means "Now" in Solr
    """
    dates = extent[1:-1].split(' TO ')
    start_date = dates[0].split('-')
    if dates[1] == '*':
        iso_date = datetime.now().isoformat()
        date = iso_date.split('T')[0]
        end_date = date.split('-')
    else:
        end_date = dates[1].split('-')
    return start_date, end_date


def remove_html_tags(text):
    """Remove HTML tags from a string using regex."""
    clean = re.compile('<.*?>') # The '?' makes the match non-greedy
    return re.sub(clean, '', text)


def render_package(root, pkg_dict, add_extra_elements=False):
    """
    Render the metadata for a single dataset to the Pure XML feed.
    """
    assert(pkg_dict['type'] == 'dataset')
    assert(pkg_dict['state'] == 'active')

    ### For the dataset to be valid in Pure, it must have a Workday mapping for Managing Organization and Publisher.

    # Publisher: Pure accepts only one publisher, so use the first one.
    publishers_standard_json = get_extras_value(pkg_dict, 'publisher-standard')
    publishers_standard = json.loads(publishers_standard_json)
    publishers_json = get_extras_value(pkg_dict, 'publisher')
    publishers = json.loads(publishers_json)
    publisher_id = None
    publisher_standard = None
    for publisher_standard, publisher in zip(publishers_standard, publishers):
        publisher_id = get_organization_id(publisher_standard)
        if publisher_id:
            break


    # Filter out cases that have missing Workday mappings
    if not publisher_id:
        message = f"#### Filtering out '{pkg_dict['title']}' with publisher(s) {publishers}"
        print_stderr(message)
        return

    publisher_string = get_publisher_string(publisher_standard)

    # log.error(pkg_dict)
    dataset = etree.Element(PURE + 'dataset', attrib={'id': pkg_dict['id'], 'type': 'dataset'})

    # Title
    title = etree.SubElement(dataset, PURE + 'title')
    title.text = pkg_dict['title']

    # Description
    description = etree.SubElement(dataset, PURE + 'description')
    description.text = remove_html_tags(pkg_dict['notes'])

    # Temporal Coverage:  Use only if it's defined
    if add_extra_elements:
        extent_range = get_extras_value(pkg_dict, 'extent_range')
        if extent_range:
            (start_date, end_date) = get_extent_parts(extent_range)
            temporal_coverage = etree.SubElement(dataset, PURE + 'temporalCoverage')
            start = etree.SubElement(temporal_coverage, PURE + 'from')
            fill_date_fields(start, start_date)
            end = etree.SubElement(temporal_coverage, PURE + 'to')
            fill_date_fields(end, end_date)

    # Geolocation:  We have to specify a polygon in Google Maps format.
    # Example would be nice; punt for now.

    # DOI
    resource_url = get_extras_value(pkg_dict, 'resource-url')
    if is_doi(resource_url):
        doi = etree.SubElement(dataset, PURE + 'DOI')
        doi.text = get_doi_suffix(resource_url)

    # Available Date:  Could be just year, or year+month
    pub_date = get_extras_value(pkg_dict, 'publication_date')
    date_parts = get_date_parts(pub_date)
    avail_date = etree.SubElement(dataset, PURE + 'availableDate')
    fill_date_fields(avail_date, date_parts)

    # Persons: For now, we just populate with authors.
    authors = get_extras_value(pkg_dict, 'harvest-author-orcid')
    if not authors:
        print_stderr("#### No authors found, skipping...")
        return
    authors = json.loads(authors)
    persons = etree.SubElement(dataset, PURE + 'persons')
    author_index = 0
    matched_author = False
    for author in authors:
        author_index += 1
        person_id = get_pure_author_id(author)
        if not person_id:
            print_stderr(f"Could not find person ID for {author}, skipping...")
            continue
        else:
            matched_author = True
        person = etree.SubElement(persons, PURE + 'person', attrib={"id": "personAssoc" + str(author_index), "contactPerson": "false"})
        person_inner = etree.SubElement(person, PURE + 'person', attrib={"lookupId": person_id})
        role = etree.SubElement(person, PURE + 'role')
        role.text = 'creator'

    if not matched_author:
        print_stderr(f"Could not find a matching author for {pkg_dict['title']} with publisher(s) {publishers}, skipping...")
        return

    org = etree.SubElement(dataset, PURE + 'managingOrganisation', attrib={'lookupId': publisher_id})
    org = etree.SubElement(dataset, PURE + 'publisher', attrib={'lookupId': publisher_string})

    # Now that the dataset element is complete, append it to the output XML feed.
    root.append(dataset)

    # Link to resource homepage
    if add_extra_elements:
        links = etree.SubElement(dataset, PURE + 'links')
        link = etree.SubElement(links, PURE + 'link', attrib={'id': resource_url})
        description = etree.SubElement(link, PURE + 'description')
        description_text = etree.SubElement(description, CMNS + 'text')
        description_text.text = 'Resource Download Homepage'
        url = etree.SubElement(link, PURE + 'url')
        url.text = resource_url
