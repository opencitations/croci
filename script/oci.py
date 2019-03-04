#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2018, Silvio Peroni <essepuntato@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software for any purpose
# with or without fee is hereby granted, provided that the above copyright notice
# and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT,
# OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE,
# DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS
# SOFTWARE.

from argparse import ArgumentParser
from re import match, findall, sub
from urllib.parse import quote, unquote
from csv import DictReader
from rdflib import Graph, RDF, RDFS, XSD, URIRef, Literal, Namespace
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from json import dumps, load, loads, JSONDecodeError
from csv import DictWriter
from io import StringIO
from SPARQLWrapper import SPARQLWrapper, JSON
from os.path import exists
from collections import deque
from requests import get
from xml.etree import ElementTree


REFERENCE_CITATION_TYPE = "reference"
SUPPLEMENT_CITATION_TYPE = "supplement"
DEFAULT_CITATION_TYPE = REFERENCE_CITATION_TYPE
CITATION_TYPES = (REFERENCE_CITATION_TYPE, SUPPLEMENT_CITATION_TYPE)
DEFAULT_DATE = datetime(1970, 1, 1, 0, 0)
AGENT_NAME = "OpenCitations"
USER_AGENT = "OCI / %s (via OpenCitations - http://opencitations.net; mailto:contact@opencitations.net)" % AGENT_NAME
URL = "https://github.com/opencitations/oci/blob/master/oci.py"
BASE_URL = "https://w3id.org/oc/virtual/"
W = "WARNING"
E = "ERROR"
I = "INFO"
PREFIX_REGEX = "0[1-9]+0"
VALIDATION_REGEX = "^%s[0-9]+$" % PREFIX_REGEX
FORMATS = {
    "xml": "xml",
    "rdfxml": "xml",
    "rdf/xml": "xml",
    "application/rdf+xml": "xml",
    "turtle": "turtle",
    "ttl": "turtle",
    "rdf": "turtle",
    "text/turtle": "turtle",
    "json": "json",
    "scholix": "scholix",
    "application/json": "json",
    "json-ld": "json-ld",
    "jsonld": "json-ld",
    "application/ld+json": "json-ld",
    "n-triples": "nt11",
    "ntriples": "nt11",
    "nt": "nt11",
    "text/plain": "nt11",
    "text/n-triples": "nt11",
    "csv": "csv",
    "text/csv": "csv"
}


class Citation(object):
    __cito_base = "http://purl.org/spar/cito/"
    __cites = URIRef(__cito_base + "cites")
    __citation = URIRef(__cito_base + "Citation")
    __author_self_citation = URIRef(__cito_base + "AuthorSelfCitation")
    __journal_self_citation = URIRef(__cito_base + "JournalSelfCitation")
    __has_citation_creation_date = URIRef(__cito_base + "hasCitationCreationDate")
    __has_citation_time_span = URIRef(__cito_base + "hasCitationTimeSpan")
    __has_citing_entity = URIRef(__cito_base + "hasCitingEntity")
    __has_cited_entity = URIRef(__cito_base + "hasCitedEntity")

    __datacite_base = "http://purl.org/spar/datacite/"
    __has_identifier = URIRef(__datacite_base + "hasIdentifier")
    __identifier = URIRef(__datacite_base + "Identifier")
    __uses_identifier_scheme = URIRef(__datacite_base + "usesIdentifierScheme")
    __oci = URIRef(__datacite_base + "oci")

    __literal_base = "http://www.essepuntato.it/2010/06/literalreification/"
    __has_literal_value = URIRef(__literal_base + "hasLiteralValue")

    __prism_base = "http://prismstandard.org/namespaces/basic/2.0/"
    __publication_date = URIRef(__prism_base + "publicationDate")

    __prov_base = "http://www.w3.org/ns/prov#"
    __was_attributed_to = URIRef(__prov_base + "wasAttributedTo")
    __had_primary_source = URIRef(__prov_base + "hadPrimarySource")
    __generated_at_time = URIRef(__prov_base + "generatedAtTime")

    def __init__(self,
                 oci, citing_url, citing_pub_date,
                 cited_url, cited_pub_date,
                 creation, timespan,
                 prov_agent_url, source, prov_date,
                 service_name, id_type, id_shape, citation_type,
                 journal_sc=False, author_sc=False):
        self.oci = oci
        self.citing_url = citing_url
        self.cited_url = cited_url
        self.duration = timespan
        self.creation_date = creation
        self.author_sc = "yes" if author_sc else "no"
        self.journal_sc = "yes" if journal_sc else "no"
        self.citing_pub_date = citing_pub_date[:10] if citing_pub_date else citing_pub_date
        self.cited_pub_date = cited_pub_date[:10] if cited_pub_date else cited_pub_date
        self.citation_type = citation_type if citation_type in CITATION_TYPES else DEFAULT_CITATION_TYPE

        if self.contains_years(citing_pub_date):
            self.creation_date = citing_pub_date[:10]

            if self.contains_years(cited_pub_date):
                citing_contains_months = Citation.contains_months(citing_pub_date)
                cited_contains_months = Citation.contains_months(cited_pub_date)
                citing_contains_days = Citation.contains_days(citing_pub_date)
                cited_contains_days = Citation.contains_days(cited_pub_date)

                # Handling incomplete dates
                citing_complete_pub_date = self.creation_date
                cited_complete_pub_date = cited_pub_date[:10]
                if citing_contains_months and not cited_contains_months:
                    cited_complete_pub_date += citing_pub_date[4:7]
                elif not citing_contains_months and cited_contains_months:
                    citing_complete_pub_date += cited_pub_date[4:7]
                if citing_contains_days and not cited_contains_days:
                    cited_complete_pub_date += citing_pub_date[7:]
                elif not citing_contains_days and cited_contains_days:
                    citing_complete_pub_date += cited_pub_date[7:]

                citing_pub_datetime = parse(citing_complete_pub_date, default=DEFAULT_DATE)
                cited_pub_datetime = parse(cited_complete_pub_date, default=DEFAULT_DATE)
                delta = relativedelta(citing_pub_datetime, cited_pub_datetime)
                self.duration = Citation.get_duration(
                    delta,
                    citing_contains_months and cited_contains_months,
                    citing_contains_days and cited_contains_days)

        if not self.citing_pub_date and self.creation_date:
            self.citing_pub_date = self.creation_date

        if self.creation_date and self.duration:
            self.cited_pub_date = Citation.get_date(self.creation_date, self.duration)

        self.prov_agent_url = prov_agent_url
        self.source = source
        self.prov_date = prov_date
        self.service_name = service_name
        self.id_type = id_type
        self.id_shape = id_shape

    @staticmethod
    def set_ns(g):
        g.namespace_manager.bind("cito", Namespace(Citation.__cito_base))
        g.namespace_manager.bind("datacite", Namespace(Citation.__datacite_base))
        g.namespace_manager.bind("literal", Namespace(Citation.__literal_base))
        g.namespace_manager.bind("prov", Namespace(Citation.__prov_base))

    def get_citation_rdf(self, baseurl, include_oci=True, include_label=True, include_prov=True):
        citation_graph, citation, citation_corpus_id = self.__get_citation_rdf_entity(baseurl)

        citing_br = URIRef(self.citing_url)
        cited_br = URIRef(self.cited_url)

        if include_label:
            citation_graph.add((citation, RDFS.label,
                                Literal("citation %s [%s]" % (self.oci, citation_corpus_id))))
        citation_graph.add((citation, RDF.type, self.__citation))
        if self.author_sc == "yes":
            citation_graph.add((citation, RDF.type, self.__author_self_citation))
        if self.journal_sc == "yes":
            citation_graph.add((citation, RDF.type, self.__journal_self_citation))

        citation_graph.add((citation, self.__has_citing_entity, citing_br))
        citation_graph.add((citation, self.__has_cited_entity, cited_br))

        if self.creation_date is not None:
            if Citation.contains_days(self.creation_date):
                xsd_type = XSD.date
            elif Citation.contains_months(self.creation_date):
                xsd_type = XSD.gYearMonth
            else:
                xsd_type = XSD.gYear

            citation_graph.add((citation, self.__has_citation_creation_date,
                                Literal(self.creation_date, datatype=xsd_type, normalize=False)))
            if self.duration is not None:
                citation_graph.add((citation, self.__has_citation_time_span,
                                    Literal(self.duration, datatype=XSD.duration)))

        if include_oci:
            for s, p, o in self.get_oci_rdf(baseurl, include_label, include_prov).triples((None, None, None)):
                citation_graph.add((s, p, o))

        if include_prov:
            for s, p, o in self.get_citation_prov_rdf(baseurl).triples((None, None, None)):
                citation_graph.add((s, p, o))

        return citation_graph

    def get_citation_prov_rdf(self, baseurl):
        citation_graph, citation, citation_corpus_id = self.__get_citation_rdf_entity(baseurl)

        citation_graph.add((citation, self.__was_attributed_to, URIRef(self.prov_agent_url)))
        citation_graph.add((citation, self.__had_primary_source, URIRef(self.source)))
        citation_graph.add((citation, self.__generated_at_time, Literal(self.prov_date, datatype=XSD.dateTime)))

        return citation_graph

    def __get_citation_rdf_entity(self, baseurl):
        citation_graph = Graph()
        Citation.set_ns(citation_graph)

        oci_no_prefix = self.oci.replace("oci:", "")
        citation_corpus_id = "ci/" + oci_no_prefix
        citation = URIRef(baseurl + citation_corpus_id)

        return citation_graph, citation, citation_corpus_id

    def get_oci_rdf(self, baseurl, include_label=True, include_prov=True):
        identifier_graph, identifier, identifier_local_id, identifier_corpus_id = self.__get_oci_rdf_entity(baseurl)

        if include_label:
            identifier_graph.add((identifier, RDFS.label,
                                  Literal("identifier %s [%s]" % (identifier_local_id, identifier_corpus_id))))
        identifier_graph.add((identifier, RDF.type, self.__identifier))
        identifier_graph.add((identifier, self.__uses_identifier_scheme, self.__oci))
        identifier_graph.add((identifier, self.__has_literal_value, Literal(self.oci)))

        if include_prov:
            for s, p, o in self.get_oci_prov_rdf(baseurl).triples((None, None, None)):
                identifier_graph.add((s, p, o))

        return identifier_graph

    def get_oci_prov_rdf(self, baseurl):
        identifier_graph, identifier, identifier_local_id, identifier_corpus_id = self.__get_oci_rdf_entity(baseurl)

        identifier_graph.add((identifier, self.__was_attributed_to, URIRef(self.prov_agent_url)))
        identifier_graph.add((identifier, self.__had_primary_source, URIRef(self.source)))
        identifier_graph.add((identifier, self.__generated_at_time,
                              Literal(self.prov_date, datatype=XSD.dateTime)))

        return identifier_graph

    def __get_oci_rdf_entity(self, baseurl):
        identifier_graph = Graph()
        Citation.set_ns(identifier_graph)

        identifier_local_id = "ci-" + self.oci.replace("oci:", "")
        identifier_corpus_id = "id/" + identifier_local_id
        identifier = URIRef(baseurl + identifier_corpus_id)

        return identifier_graph, identifier, identifier_local_id, identifier_corpus_id

    def get_citation_csv(self):
        s_res = StringIO()
        writer = DictWriter(s_res, ["oci", "citing", "cited", "creation", "timespan", "journal_sc", "author_sc"])
        writer.writeheader()
        writer.writerow(loads(self.get_citation_json()))
        return s_res.getvalue()

    def get_citation_csv_prov(self):
        s_res = StringIO()
        writer = DictWriter(s_res, ["oci", "agent", "source", "datetime"])
        writer.writeheader()
        writer.writerow(loads(self.get_citation_json_prov()))
        return s_res.getvalue()

    def get_citation_json(self):
        result = {
            "oci": self.oci.replace("oci:", ""),
            "citing": self.get_id(self.citing_url),
            "cited": self.get_id(self.cited_url),
            "creation": self.creation_date,
            "timespan": self.duration,
            "journal_sc": self.journal_sc,
            "author_sc": self.author_sc
        }

        return dumps(result, indent=4, ensure_ascii=False)

    def get_citation_json_prov(self):
        result = {
            "oci": self.oci.replace("oci:", ""),
            "agent": self.prov_agent_url,
            "source": self.source,
            "datetime": self.prov_date
        }

        return dumps(result, indent=4, ensure_ascii=False)

    def get_citation_scholix(self):
        if self.citation_type == REFERENCE_CITATION_TYPE:
            rel_type = "References"
        elif self.citation_type == SUPPLEMENT_CITATION_TYPE:
            rel_type = "IsSupplementedBy"
        else:
            rel_type = "References"

        result = {
            "LinkPublicationDate": self.prov_date,
            "LinkProvider": [
                {"Name": AGENT_NAME},
                {"Name": self.service_name}
            ],
            "RelationshipType": {"Name": rel_type},
            "LicenseURL": "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
            "Source": {
                "Identifier": {
                    "ID": self.get_id(self.citing_url),
                    "IDScheme": self.id_type,
                    "IDURL": self.citing_url
                },
                "Type": {"Name": "literature"}
            },
            "Target": {
                "Identifier": {
                    "ID": self.get_id(self.cited_url),
                    "IDScheme": self.id_type,
                    "IDURL": self.cited_url
                },
                "Type": {"Name": "literature"}
            }
        }

        if self.citing_pub_date:
            result["Source"]["PublicationDate"] = self.citing_pub_date

        if self.cited_pub_date:
            result["Target"]["PublicationDate"] = self.cited_pub_date

        return dumps(result, indent=4, ensure_ascii=False)

    def get_id(self, entity_url):
        decode = "XXX__decode]]" in self.id_shape
        entity_regex = sub("\[\[[^\]]+\]\]", ".+", self.id_shape)
        entity_token = sub(entity_regex, "\\1", entity_url)
        return unquote(entity_token) if decode else entity_token

    @staticmethod
    def contains_years(date):
        return date is not None and len(date) >= 4

    @staticmethod
    def contains_months(date):
        return date is not None and len(date) >= 7

    @staticmethod
    def contains_days(date):
        return date is not None and len(date) >= 10

    @staticmethod
    def get_duration(delta, consider_months, consider_days):
        result = ""
        if delta.years < 0 or \
                (delta.years == 0 and delta.months < 0 and consider_months) or \
                (delta.years == 0 and delta.months == 0 and delta.days < 0 and consider_days):
            result += "-"
        result += "P%sY" % abs(delta.years)

        if consider_months:
            result += "%sM" % abs(delta.months)

        if consider_days:
            result += "%sD" % abs(delta.days)

        return result

    @staticmethod
    def get_date(creation_date, duration):
        params = {}
        for item in findall("^-?P([0-9]+Y)?([0-9]+M)?([0-9]+D)?$", duration)[0]:
            if "Y" in item:
                params["years"] = int(item[:-1])
            elif "M" in item:
                params["months"] = int(item[:-1])
            elif "D" in item:
                params["days"] = int(item[:-1])

        delta = relativedelta(**params)
        d = parse(creation_date, default=DEFAULT_DATE)
        if duration.startswith("-"):
            result = d + delta
        else:
            result = d - delta

        if "D" in duration or Citation.contains_days(creation_date):
            cut = 10
        elif "M" in duration or Citation.contains_months(creation_date):
            cut = 7
        else:
            cut = 4

        return result.strftime('%Y-%m-%d')[:cut]

    @staticmethod
    def format_rdf(g, f="text/turtle"):
        cur_format = f
        if f in FORMATS:
            cur_format = FORMATS[f]
        return g.serialize(format=cur_format, encoding="utf-8").decode("utf-8")


class OCIManager(object):
    def __init__(self, oci_string=None, lookup_file=None, conf_file=None, doi_1=None, doi_2=None, prefix=""):
        self.is_valid = None
        self.messages = []
        self.f = {
            "decode": self.__decode,
            "encode": quote,
            "join": OCIManager.__join,
            "shape": OCIManager.__shape,
            "remove": OCIManager.__remove,
            "normdate": OCIManager.__normdate,
            "datestrings": OCIManager.__datestrings,
            "api": OCIManager.__call_api,
            "avoid_prefix_removal": OCIManager.__avoid_prefix_removal
        }
        self.lookup = {}
        self.inverse_lookup = {}
        if lookup_file is not None and exists(lookup_file):
            with open(lookup_file) as f:
                reader = DictReader(f)
                for row in reader:
                    self.lookup[row["code"]] = row["c"]
                    self.inverse_lookup[row["c"]] = row["code"]
        else:
            self.add_message("__init__", W, "No lookup file has been found (path: '%s')." % lookup_file)
        self.conf = None
        if conf_file is not None and exists(conf_file):
            with open(conf_file) as f:
                self.conf = load(f)
        else:
            self.add_message("__init__", W, "No configuration file has been found (path: '%s')." % lookup_file)

        if oci_string:
            self.oci = oci_string.lower().strip()
        elif doi_1 and doi_2:
            self.oci = self.get_oci(doi_1, doi_2, prefix)
        else:
            self.oci = None
            self.add_message("__init__", W, "No OCI specified!")

    def __decode(self, s):
        result = []

        for code in findall("(9*[0-8][0-9])", s):
            if code in self.lookup:
                result.append(self.lookup[code])
            else:
                result.append(code)

        return "10." + "".join(result)

    def __decode_inverse(self, doi):
        result = []

        for char in doi.replace("10.", ""):
            result.append(self.inverse_lookup[char])

        return "".join(result)

    def get_oci(self, doi_1, doi_2, prefix):
        self.oci = "oci:%s%s-%s%s" % (prefix, self.__decode_inverse(doi_1), prefix, self.__decode_inverse(doi_2))
        return self.oci

    @staticmethod
    def __join(l, j_value=""):
        if type(l) is list:
            return j_value.join(l)
        else:
            return l

    @staticmethod
    def __avoid_prefix_removal(s):
        return "0123567890" + s

    @staticmethod
    def __shape(id_s, base=""):
        return base + quote(id_s)

    @staticmethod
    def __remove(id_s, to_remove=""):
        return id_s.replace(to_remove, "")

    @staticmethod
    def __normdate(date_s):
        return sub("[^\d-]", "", date_s)

    @staticmethod
    def __datestrings(l):
        result = []

        for i in l:
            i_str = str(i)
            if len(i_str) == 1:
                i_str = "0" + i_str
            result.append(i_str)

        return result

    def __execute_query(self, citing_entity, cited_entity):
        result = None

        if self.conf is None:
            self.add_message("__execute_query", E, "No citations can be retrieved since no configuration "
                                                   "file has been specified.")
        else:
            try:
                i = iter(self.conf["services"])
                while result is None:
                    item = next(i)
                    name, query, api, tp, use_it, preprocess, prefix, id_type, id_shape, citation_type = \
                        item.get("name"), item.get("query"), item.get("api"), item.get("tp"), item.get("use_it"), \
                        item["preprocess"] if "preprocess" in item else [], \
                        item["prefix"] if "prefix" in item else [], item.get("id_type"), item.get("id_shape"), \
                        item["citation_type"] if "citation_type" in item else DEFAULT_CITATION_TYPE

                    if use_it == "yes" and all(sub("^(%s).+$" % PREFIX_REGEX, "\\1", p) in prefix
                                               for p in (citing_entity, cited_entity)):
                        citing = sub("^%s(.+)$" % PREFIX_REGEX, "\\1", citing_entity)
                        cited = sub("^%s(.+)$" % PREFIX_REGEX, "\\1", cited_entity)

                        for f_name in preprocess:
                            citing = self.f[f_name](citing)
                            cited = self.f[f_name](cited)

                        if tp is None:
                            rest_query = api.replace("[[CITING]]", quote(citing)).replace("[[CITED]]", quote(cited))
                            structured_res, type_res = OCIManager.__call_api(rest_query)
                            if structured_res:
                                result = self.__read_api_data(structured_res, type_res, query.get("citing"),
                                                              citing, cited, api), \
                                         self.__read_api_data(structured_res, type_res, query.get("cited"),
                                                              citing, cited, api), \
                                         self.__read_api_data(structured_res, type_res, query.get("citing_date"),
                                                              citing, cited, api), \
                                         self.__read_api_data(structured_res, type_res, query.get("cited_date"),
                                                              citing, cited, api), \
                                         self.__read_api_data(structured_res, type_res, query.get("creation"),
                                                              citing, cited, api), \
                                         self.__read_api_data(structured_res, type_res, query.get("timespan"),
                                                              citing, cited, api), \
                                         rest_query, name, id_type, id_shape, citation_type
                        else:
                            sparql = SPARQLWrapper(tp)
                            sparql_query = sub("\\[\\[CITED\\]\\]", cited, sub("\\[\\[CITING\\]\\]", citing, query))

                            sparql.setQuery(sparql_query)
                            sparql.setReturnFormat(JSON)
                            q_res = sparql.query().convert()["results"]["bindings"]
                            if len(q_res) > 0:
                                answer = q_res[0]
                                result = answer["citing"]["value"], \
                                         answer["cited"]["value"], \
                                         answer["citing_date"]["value"] if "citing_date" in answer else None, \
                                         answer["cited_date"]["value"] if "cited_date" in answer else None, \
                                         answer["creation"]["value"] if "creation" in answer else None, \
                                         answer["timespan"]["value"] if "timespan" in answer else None, \
                                         tp + "?query=" + quote(sparql_query), name, id_type, id_shape, citation_type

            except StopIteration:
                pass  # No nothing

        return result

    @staticmethod
    def __call_api(u):
        structured_res = None
        type_res = None

        res = get(u, headers={"User-Agent": USER_AGENT}, timeout=30)

        if res.status_code == 200:
            res.encoding = "utf-8"
            cur_str = res.text

            try:
                structured_res = loads(cur_str)
                type_res = "json"
            except JSONDecodeError:
                structured_res = ElementTree.fromstring(cur_str)
                type_res = "xml"

        return structured_res, type_res

    def __read_api_data(self, data, type_format, access_list, citing, cited, api):
        result = None

        if data and access_list:
            access_queue = deque(access_list)
            while result is None and access_queue:
                access_string = access_queue.popleft()
                access_operations = deque(access_string.split("::"))

                access_operation = access_operations.popleft()
                if citing:
                    access_operation = sub("\[\[CITING\]\]", citing, access_operation)
                if cited:
                    access_operation = sub("\[\[CITED\]\]", cited, access_operation)

                f_to_execute = []
                if "->" in access_operation:
                    for idx, item in enumerate(access_operation.split("->")):
                        if idx:
                            f_to_execute.append(item)
                        else:
                            access_operation = item
                if match("^([^\(]+)\((.*)\)$", access_operation):
                    f_name, f_params = findall("([^\(]+)\((.*)\)", access_operation)[0]
                    f_params = f_params.split(",") if f_params else []
                    result = self.f[f_name](*f_params)
                    if type(result) is tuple:
                        result, type_format = result
                elif match("\[[0-9]+\]", access_operation):
                    cur_n = int(sub("\[([0-9]+)\]", "\\1", access_operation))
                    if type(data) is list and cur_n < len(data):
                        result = data[cur_n]
                elif match("^\[.+\]$", access_operation) and "==" in access_operation:
                    left, right = sub("^\[(.+)\]$", "\\1", access_operation).split("==")
                    if type(data) is list:
                        list_queue = deque(data)
                        while result is None and list_queue:
                            item = list_queue.popleft()
                            item_value = item.get(left)
                            if item_value is not None and item_value.lower() == right.lower():
                                result = item
                else:
                    if type_format == "json":
                        result = data.get(access_operation)
                    elif type_format == "xml":
                        el = None

                        if match("^({.+})?%s$" % access_operation, data.tag):
                            el = data
                        else:
                            children = deque(data)
                            while el is None and children:
                                child = children.popleft()
                                if match("^({.+})?%s$" % access_operation, child.tag):
                                    el = child

                        result = el

                if result is not None and not access_operations and type_format == "xml":
                    result = sub("\s+", " ", result.text).strip()

                if f_to_execute and result is not None:
                    for f in f_to_execute:
                        f_name, f_params = findall("([^\(]+)\((.*)\)", f)[0]
                        f_params = f_params.split(",") if f_params else []
                        f_params.insert(0, result)
                        result = self.f[f_name](*f_params)
                        if type(result) is tuple:
                            result, type_format = result

                if access_operations:
                    result = self.__read_api_data(result, type_format, ["::".join(access_operations)],
                                                  citing, cited, api)

        return result

    def validate(self):
        if self.is_valid is None:
            if not self.oci.startswith("oci:"):
                self.oci = "oci:" + self.oci
                self.add_message("validate", W, "The OCI specified as input doesn't start with the 'oci:' "
                                                "prefix. This has beed automatically added, resulting in "
                                                "the OCI '%s'." % self.oci)

            self.is_valid = False
            entities = self.oci.replace("oci:", "").split("-")
            if all(match(VALIDATION_REGEX, entity) for entity in entities):
                service_queue = deque(self.conf["services"])

                while service_queue and not self.is_valid:
                    service_prefixes = service_queue.popleft()["prefix"]
                    self.is_valid = all(sub("^(%s).+$" % PREFIX_REGEX, "\\1", entity) in service_prefixes
                                        for entity in entities)

                if self.is_valid:
                    self.add_message("validate", I, "The OCI '%s' is syntactically valid." % self.oci)
                else:
                    self.add_message("validate", E, "The supplier prefixes '%s' and '%s' used in the identifiers of "
                                                    "the citing and cited entities described by the OCI '%s' must be "
                                                    "assigned to the same supplier. A list of all the available "
                                                    "suppliers is available at http://opencitations.net/oci." %
                                     (tuple(sub("^(%s).+$" % PREFIX_REGEX, "\\1", entity)
                                            for entity in entities) + (self.oci,)))

            else:
                self.add_message("validate", E, "The OCI '%s' is not syntactically correct, since at least "
                                                "one of the two identifiers of the citing and cited entities "
                                                "described by the OCI are not compliant with the following "
                                                "regular expression: '%s'." % (self.oci, VALIDATION_REGEX))

        return self.is_valid

    def get_citation_object(self):
        if self.validate():
            citing_entity_local_id = sub("^oci:([0-9]+)-([0-9]+)$", "\\1", self.oci)
            cited_entity_local_id = sub("^oci:([0-9]+)-([0-9]+)$", "\\2", self.oci)

            res = self.__execute_query(citing_entity_local_id, cited_entity_local_id)
            if res is not None:
                citing_url, cited_url, full_citing_pub_date, full_cited_pub_date, \
                creation, timespan, sparql_query_url, name, id_type, id_shape, citation_type = res

                citation = Citation(self.oci,
                                    citing_url, full_citing_pub_date,
                                    cited_url, full_cited_pub_date,
                                    creation, timespan,
                                    URL, sparql_query_url,
                                    datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                                    name, id_type, id_shape, citation_type)

                return citation
            else:
                self.add_message("get_citation_object", I, "No citation data have been found for the OCI '%s'. "
                                                           "While the OCI specified is syntactically valid, "
                                                           "it is possible that it does not identify any "
                                                           "citation at all." % self.oci)
        else:
            self.add_message("get_citation_object", E, "No citation data can be returned since the OCI specified is "
                                                       "not valid.")

    def get_citation_data(self, f="json"):
        citation = self.get_citation_object()
        if citation:
            result = None
            cur_format = "json"
            if f in FORMATS:
                cur_format = FORMATS[f]

            if cur_format == "json":
                result = citation.get_citation_json()
            elif cur_format == "csv":
                result = citation.get_citation_csv()
            elif cur_format == "scholix":
                result = citation.get_citation_scholix()
            else:  # RDF format
                result = Citation.format_rdf(citation.get_citation_rdf(BASE_URL), cur_format)

            return result

    def print_messages(self):
        for mes in self.messages:
            print("{%s} [%s] %s" % (mes["operation"], mes["type"], mes["text"]))

    def add_message(self, fun, mes_type, text):
        self.messages.append({"operation": fun, "type": mes_type, "text": text})


if __name__ == "__main__":
    arg_parser = ArgumentParser("oci.py", description="This script allows one to validate and retrieve citationd data "
                                                      "associated to an OCI (Open Citation Identifier).")

    arg_parser.add_argument("-o", "--oci", dest="oci", required=True,
                            help="The input OCI to use.")
    arg_parser.add_argument("-l", "--lookup", dest="lookup", default="lookup.csv",
                            help="The lookup file to be used for encoding identifiers.")
    arg_parser.add_argument("-c", "--conf", dest="conf", default="oci.json",
                            help="The configuration file to run the query services to retrieve citation information.")
    arg_parser.add_argument("-f", "--format", dest="format", default=None,
                            help="If the format is specified, the script tries to retrieve citation information that "
                                 "will be returned in the requested format. Possible formats: 'csv', 'json', "
                                 "'scholix', 'jsonld', 'ttl', 'rdfxml', 'nt'")

    args = arg_parser.parse_args()

    om = OCIManager(args.oci, args.lookup, args.conf)

    result = None
    if args.format is None:
        result = om.validate()
    else:
        result = om.get_citation_data(args.format)

    om.print_messages()

    if result is not None:
        print(result)
