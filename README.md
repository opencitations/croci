# CROCI, the Crowdsourced Open Citations Index

[CROCI, the Crowdsourced Open Citations Index](http://oprncitations.net/index/croci), is a new OpenCitations Index containing citations deposited by individuals, identified by ORCiD identifiers, who have a legal right to publish them under a CC0 public domain waiver. A detailed description of the motivation behind the creation of this new OpenCitations Index are available in our blog post entitled ["Crowdsourcing open citations with CROCI"](https://opencitations.wordpress.com/2019/02/07/crowdsourcing-open-citations-with-croci/).

## How to contribute

To populate CROCI, we ask researchers, authors, editors and publishers to provide us with their citation data organised in a simple four-column CSV file (“citing_id”, “citing_publication_date”, “cited_id”, “cited_publication_date”), where each row depicts a citation from the citing entity (“citing_id”, giving the DOI of the cited entity) published on a certain date (“citing_publication_date”, with the date value expressed in ISO format “yyyy-mm-dd”), to the cited entity (“cited_id”, giving  the DOI of the cited entity) published on a certain date (“cited_publication_date”, again with the date value expressed in ISO format “yyyy-mm-dd”). The submitted dataset may contain an individual citation, groups of citations (for example those derived from the reference lists of one or more publications), or entire citation collections. Should any of the submitted citations be already present within CROCI, these duplicates will be automatically detected and ignored.

The date information given for each citation should be as complete as possible, and minimally should be the publication years of the citing and cited entities. However, if such date information  is unavailable, we will try to retrieve it automatically using OpenCitations technology already available. DOIs may be expressed in any of a variety of valid alternative formats, e.g. “https://doi.org/10.1038/502295a”, “http://dx.doi.org/10.1038/502295a”, “doi: 10.1038/502295a”, “doi:10.1038/502295a”, or simply “10.1038/502295a”.

An example of such a CVS citations file can be found at [example.csv](https://github.com/opencitations/croci/blob/master/example.csv). As an alternative to submissions in CSV format, contributors can submit the same citation data using the Scholix format (Burton et al., 2017) – an example of such format can be found at [example.scholix](https://github.com/opencitations/croci/blob/master/example.scholix).

Submission of such a citation dataset in CSV or Scholix format should be made as a file upload either to Figshare (https://figshare.com) or to Zenodo (https://zenodo.org). For provenance purposes, the ORCID personal identifier of the submitter of these citation data should be explicitly provided in the metadata or in the description of the Figshare/Zenodo object. Once such a citation data file upload has been made, the submitter should inform OpenCitations of this fact by adding an new issue to the GitHub issue tracker of the CROCI repository (https://github.com/opencitations/croci/issues).

OpenCitations will then process each submitted citation dataset and ingest the new citation information into CROCI. CROCI citations will be available at http://opencitations.net/index/croci using an appropriate [REST API](http://opencitations.net/index/croci/api/v1) and [SPARQL endpoint](http://opencitations.net/index/sparql), and will additionally be published as periodic data dumps in Figshare, all releases being under CC0 waivers.

## Tools

Some tool has been developed for helping users to produce such citation data according to the format used for including the data in CROCI.

* As anticipated in [two](https://twitter.com/scholarcy/status/1099027149724499968) [tweets](https://twitter.com/scholarcy/status/1099967467944927232), [Scholarcy](https://www.scholarcy.com/) has made available [an API](http://ref.scholarcy.com) which is able to extract references from PDF and Word documents and that returns as a CSV compliant with the CROCI format mentioned above.
