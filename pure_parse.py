import urllib.request
import urllib.error
from lxml import etree as ET


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

ISO_NAMESPACES = {'d':  'v1.organisation-sync.pure.atira.dk',
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
        matching_elements = xml_tree.xpath(xpath, namespaces=ISO_NAMESPACES)
        organisation_element = matching_elements[0].getparent().getparent().getparent().getparent()
        organisation_id_element = organisation_element.xpath('.//d:organisationId', namespaces=ISO_NAMESPACES)
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
