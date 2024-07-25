import json
import sys
from datetime import datetime
import pathlib

from lxml import etree


PURE_NS = "v1.dataset.pure.atira.dk"
PURE = "{%s}" % PURE_NS

PURE_CMNS = "v3.commons.pure.atira.dk"
CMNS = "{%s}" % PURE_CMNS


def print_stderr(msg):
    print(msg, file=sys.stderr)

def xml_init(use_namespaces):
    if use_namespaces:
        rootElement = etree.Element(PURE + "datasets", nsmap={'v1': PURE_NS, 'v3': PURE_CMNS})
    else:
        rootElement = etree.Element(PURE + "datasets", nsmap={None: PURE_NS, 'v3': PURE_CMNS})
    return rootElement


def write_xml(root, output_file=None):
    content = etree.tostring(root, pretty_print=True, encoding='unicode')
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


def get_doi_suffix(urlString):
    suffix = urlString.split('doi.org/', 1)[1]
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
    return (start_date, end_date)


def render_package(root, pkg_dict, add_extra_elements=False):
    # Filter out non-dataset, non-active packages
    if pkg_dict['type'] != 'dataset' or pkg_dict['state'] != 'active':
        return

    # log.error(pkg_dict)
    dataset = etree.SubElement(root, PURE + 'dataset', attrib={'id': pkg_dict['id'], 'type': 'dataset'})

    # Title
    title = etree.SubElement(dataset, PURE + 'title')
    title.text = pkg_dict['title']

    # Description
    description = etree.SubElement(dataset, PURE + 'description')
    description.text = pkg_dict['notes']

    # Temporal Coverage:  Use only if it's defined
    if add_extra_elements:
        extent_range = get_extras_value(pkg_dict, 'extent_range')
        if extent_range:
            (startDate, endDate) = get_extent_parts(extent_range)
            temporal_coverage = etree.SubElement(dataset, PURE + 'temporalCoverage')
            start = etree.SubElement(temporal_coverage, PURE + 'from')
            fill_date_fields(start, startDate)
            end = etree.SubElement(temporal_coverage, PURE + 'to')
            fill_date_fields(end, endDate)

    # Geolocation:  We have to specify a polygon in Google Maps format.
    # Example would be nice; punt for now.

    # Persons: For now, we just populate with authors.
    if add_extra_elements:
        authors = get_extras_value(pkg_dict, 'harvest-author')
        authors = json.loads(authors)
        persons = etree.SubElement(dataset, PURE + 'persons')
        for author in authors:
            person = etree.SubElement(persons, PURE + 'person', attrib={"id": author})
            person_inner = etree.SubElement(person, PURE + 'person', attrib={"lookupId": author})
            # As a first pass, we put the entire author name into the "firstName" field.
            # personParts = getPersonParts(author)
            first_name = etree.SubElement(person_inner, PURE + 'firstName')
            first_name.text = author
            role = etree.SubElement(person, PURE + 'role')
            role.text = 'creator'

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

    # Managing Organization
    managing_org = get_extras_value(pkg_dict, 'resource-support-organization')
    if not managing_org:
        managing_org = get_extras_value(pkg_dict, 'metadata-support-organization')
    if not managing_org:
        managing_org = pkg_dict['organization']['title']
    org = etree.SubElement(dataset, PURE + 'managingOrganisation', attrib={'lookupId': managing_org})

    # Publisher: Pure accepts only one publisher, so use the first one.
    publishers = get_extras_value(pkg_dict, 'publisher-standard')
    publisher = json.loads(publishers)[0]
    org = etree.SubElement(dataset, PURE + 'publisher', attrib={'lookupId': publisher})

    # Link to resource homepage
    if add_extra_elements:
        links = etree.SubElement(dataset, PURE + 'links')
        link = etree.SubElement(links, PURE + 'link', attrib={'id': resource_url})
        description = etree.SubElement(link, PURE + 'description')
        description_text = etree.SubElement(description, CMNS + 'text')
        description_text.text = 'Resource Download Homepage'
        url = etree.SubElement(link, PURE + 'url')
        url.text = resource_url
