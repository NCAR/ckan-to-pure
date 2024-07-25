# ckan-to-pure
A python utility for reading dataset metadata from a CKAN repository and writing the metadata to XML based on the Elsevier Pure XSD schema.

Dataset metadata is obtained from a CKAN website through HTTP requests, so an internet connection is required.

Tested with python 3.8.

Example usage:

       python ckan2pure.py --ckan-url https://data.ucar.edu > pure.xml
       
Optional arguments:

       --ckan-url         Base URL for CKAN repository; default is "https://data.ucar.edu"
       --test             Generate output for the first ten datasets only
       --use-namespaces   Use qualified namespaces.  Should be selected if --validate is selected.
       --validate         Perform XSD schema validation on the XML output
       --add-extra        Add extra concepts from the Pure Schema to XML output
       
       --version          Print the program version and exit.
