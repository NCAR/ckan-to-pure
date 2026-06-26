import urllib.request
import urllib.error
from lxml import etree as ET
import os
import yaml

from lxml.etree import XPathEvalError


def urlopen_with_basic_auth(url, username, password):
    """
    Opens a URL using urllib.request.urlopen with basic HTTP authentication.

    Args:
        url (str): The URL to open.
        username (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        http.client.HTTPResponse: The response object from the URL.

    Raises:
        urllib.error.URLError: If there is an issue with the URL or network.
        urllib.error.HTTPError: If the server returns an HTTP error (e.g., 401).
    """
    try:
        # Create a password manager
        password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, url, username, password)

        # Create an authentication handler
        auth_handler = urllib.request.HTTPBasicAuthHandler(password_manager)

        # Build an opener with the authentication handler
        opener = urllib.request.build_opener(auth_handler)

        # Install the opener globally (optional, but convenient for subsequent urlopen calls)
        urllib.request.install_opener(opener)

        # Open the URL using the installed opener
        response = urllib.request.urlopen(url)
        return response

    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        raise
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        raise


def getXMLTree(xml_string):
    root = None
    try:
        root = ET.fromstring(xml_string)
    except ET.XMLSyntaxError as e:
        print(f"XML Syntax Error: {e.msg}")
        print(f"Line: {e.lineno}, Column: {e.column}")
    except ET.ParserError as e:
        print(f"Parser Error: {e}")
    return root

ORG_NAMESPACES = {'d': 'v1.organisation-sync.pure.atira.dk',
                  'cmns': 'v3.commons.pure.atira.dk',
                  'f': 'http://myCustomFunctions.com',
                  'xs': 'http://www.w3.org/2001/XMLSchema'}

PERSON_NAMESPACES = {'d': 'v1.unified-person-sync.pure.atira.dk',
                     'cmns': 'v3.commons.pure.atira.dk',
                     'f': 'http://myCustomFunctions.com',
                     'xs': 'http://www.w3.org/2001/XMLSchema'}

def populate_workday_mapping():
    """
        Query the PURE API to populate the workday mapping for organization IDs.
    """
    mapping = {}
    orgname_xpath = './/d:organisation/d:nameVariants/d:nameVariant/d:name/cmns:text'

    # Get PURE XML feed data
    auth_file = '.auth_tokens'
    with open(auth_file) as f:
        URL = f.readline().strip()
        username = f.readline().strip()
        password = f.readline().strip()
    cost_centers = urlopen_with_basic_auth(URL + 'costcenters', username, password)
    cost_centers = cost_centers.read()
    xml_tree = getXMLTree(cost_centers)

    # Search for labs and extract their IDs
    labs = ['ACOM', 'CGD', 'CISL', 'ISD', 'EOL', 'HAO', 'NCARLIB', 'RAL', 'UCP', 'NCAR']
    for lab in labs:
        xpath = f"{orgname_xpath}[text()=\"{lab}\"]"
        matching_elements = xml_tree.xpath(xpath, namespaces=ORG_NAMESPACES)
        organisation_element = matching_elements[0].getparent().getparent().getparent().getparent()
        organisation_id_element = organisation_element.xpath('.//d:organisationId', namespaces=ORG_NAMESPACES)
        organisation_id = organisation_id_element[0].text.strip()

        # Rename keys for a few Orgs to match DASH Search entries
        if lab == "ISD":
            mapping['GDEX'] = organisation_id
            mapping['RDA'] = organisation_id
        elif lab == "NCARLIB":
            mapping['Library'] = organisation_id
        else:
            mapping[lab] = organisation_id

    return mapping


# Organization IDs get populated with Pure API queries
WORKDAY_ORG_MAPPING = {}
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


ORG_AUTHORS = None
ORG_AUTHOR_IDS = None
def get_author_organization_id(org_author_string):
    """
    Load YAML data with NCAR author teams, their mapped NCAR Lab, and
    Lab author IDs.

    Return the NCAR Lab Id if the team name is found.
    """
    org_author_id = None
    global ORG_AUTHORS
    if ORG_AUTHORS is None:
        with open('author_orgs.yaml', 'r') as file:
            ORG_AUTHORS = yaml.safe_load(file)
    global ORG_AUTHOR_IDS
    if ORG_AUTHOR_IDS is None:
        with open('author_org_ids.yaml', 'r') as file:
            ORG_AUTHOR_IDS = yaml.safe_load(file)
    for org in ORG_AUTHORS:
        if org_author_string in ORG_AUTHORS[org]:
            org_author_id = str(ORG_AUTHOR_IDS[org])
    return org_author_id


def is_middle_initial(word_string):
    is_mi = len(word_string) == 2 and word_string[-1] == '.'
    return is_mi


def split_name_string(name_string):
    """
    This function takes a person's full name, and if it has one whitespace separating two words and no commas,
    e.g. "John Doe", it returns (first_name="John", last_name="Doe").  If the full name
    has three words, no commas, and the middle word is in the form of a middle initial, e.g. "Jane L. Plain",
    then return (first_name="Jane", last_name="Plain"). .

    If the word string has a comma, e.g. "Plain, Jane L.", then return (first_name="Jane", last_name="Plain").
    This function also removes all occurrences of "Jr." in a name.
    """
    name_string = name_string.replace(", Jr.", "")
    name_string = name_string.replace(" Jr.", " ")
    first_name = None
    last_name = None

    has_comma = ',' in name_string
    words = name_string.split()
    org_name_indicators = ['Team', 'Facility', 'Center', 'Community', 'Laboratory',
                           'Group', 'Program', 'Division', 'Section', 'System']
    is_organization = any([org_name in words for org_name in org_name_indicators])
    if is_organization:
        last_name = name_string
    elif has_comma:
        string_parts = name_string.split(',')
        last_name = string_parts[0].strip()
        # Take just the first part of what follows the comma.
        first_name = string_parts[1].split()[0]
    elif len(words) >= 2 :
        first_name = words[0]
        last_name = words[-1]
    else:
        last_name = name_string
    return first_name, last_name


PERSONS_XML_FEED = None

def get_pure_author_id(author):
    """Given a list of author dictionaries with the fields 'name' and 'orcid', find the Workday IDs
       using the PURE API.   Also return the ORCID id, or None if it is not found.
    """
    author_id = None
    orcid_id = None
    orcid_xpath = ".//d:person/d:orcId"

    global PERSONS_XML_FEED
    if PERSONS_XML_FEED is None:
        # Always get the latest Workday persons data
        auth_file = '.auth_tokens'
        with open(auth_file) as f:
            URL = f.readline().strip()
            username = f.readline().strip()
            password = f.readline().strip()
        PERSONS_XML_FEED = urlopen_with_basic_auth(URL + 'persons', username, password)
        PERSONS_XML_FEED = PERSONS_XML_FEED.read()

        # Create a local file with persons content for debugging purposes
        if not os.path.exists("/tmp/persons.txt"):
            persons_text = PERSONS_XML_FEED.decode('utf-8')
            with open("/tmp/persons.txt", 'w') as file:
                file.write(persons_text)
        PERSONS_XML_FEED = getXMLTree(PERSONS_XML_FEED)

    # First, check if there is an ORCID and it's in Workday
    if author['orcid_url'] and 'orcid' in author['orcid_url']:
        orcid_id = author['orcid_url'].split('/')[-1]
        xpath = f"{orcid_xpath}[text()=\"{orcid_id}\"]"
        matchingOrcidElements = PERSONS_XML_FEED.xpath(xpath, namespaces=PERSON_NAMESPACES)
        if matchingOrcidElements:
            personElement = matchingOrcidElements[0].getparent()
            author_id = personElement.get("id")
            return author_id, orcid_id
        #else:
        #    # Library wants ORCID-to-dataset mappings for all available ORCID ids
        #    return None, orcid_id

    # If author is an NCAR team, return the associated Lab ID.
    author_id = get_author_organization_id(author['name'])
    if author_id:
        return author_id, orcid_id

    # Try name matching if ORCID matching and organization author search fails.
    first_name, last_name = split_name_string(author['name'])
    name_xpath = f".//d:person/d:name[cmns:firstname=\"{first_name}\"][cmns:lastname=\"{last_name}\"]"
    try:
        matchingNameElements = PERSONS_XML_FEED.xpath(name_xpath, namespaces=PERSON_NAMESPACES)
    except XPathEvalError as e:
        print(f"XPathEvalError: {e.reason}")
        raise
    if matchingNameElements:
        personElement = matchingNameElements[0].getparent()
        author_id = personElement.get("id")

    return author_id, orcid_id
