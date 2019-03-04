#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2019, Silvio Peroni <essepuntato@gmail.com>
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
from script.oci import OCIManager, Citation
from requests import get
from json import loads, load
from re import sub, findall
from urllib.parse import unquote, quote
from datetime import datetime
from csv import DictReader, DictWriter
from os.path import isdir, exists
from os import walk, sep, makedirs


HTTP_HEADERS = {"User-Agent": "CROCI / Create New Citations (via OpenCitations - "
                              "http://opencitations.net; mailto:contact@opencitations.net)"}
BASE_URL = "http://dx.doi.org/"
CROCI_BASE = "https://w3id.org/oc/index/croci/"


class DOIManager(object):
    def __init__(self):
        self.api = "https://doi.org/api/handles/"

    def normalize(self, doi_entity):
        try:
            doi_string = sub("\s+", "", unquote(doi_entity[doi_entity.index("10."):]))
            return doi_string.lower().strip()
        except:  # Any error in processing the DOI will return None
            return None

    def call_doi(self, doi_entity):
        doi = self.normalize(doi_entity)
        r = get(self.api + quote(doi), headers=HTTP_HEADERS, timeout=30)
        if r.status_code == 200:
            r.encoding = "utf-8"
            json_res = loads(r.text)
            return json_res.get("responseCode")

    def is_valid(self, doi_entity):
        result = self.call_doi(doi_entity)
        return result == 1


class DataCiteManager(object):
    def __init__(self):
        self.date = {}
        self.api = "https://api.datacite.org/works/%s"
        self.dm = DOIManager()

    def call_datacite(self, doi_entity):
        doi = self.dm.normalize(doi_entity)
        r = get(self.api + quote(doi), headers=HTTP_HEADERS, timeout=30)
        if r.status_code == 200:
            r.encoding = "utf-8"
            json_res = loads(r.text)
            return json_res

    def __get_date(self, json_obj):
        return json_obj.get("published")

    def __retrive_all(self, doi):
        json_obj = self.call_datacite(doi)
        if json_obj.get("data") and json_obj["data"].get("attributes"):
            self.date[doi] = self.__get_date(json_obj["data"]["attributes"])

    def __get_item(self, doi_entity, c):
        doi = self.dm.normalize(doi_entity)
        if doi not in c:
            json_obj = self.call_datacite(doi)
            self.date[doi] = self.__get_date(json_obj["data"]["attributes"])
        return c.get(doi)

    def get_date(self, doi_entity):
        return self.__get_item(doi_entity, self.date)


class CrossrefManager(object):
    def __init__(self):
        self.issn = {}
        self.date = {}
        self.orcid = {}
        self.api = "https://api.crossref.org/works/%s"
        self.dm = DOIManager()

    def call_crossref(self, doi_entity):
        doi = self.dm.normalize(doi_entity)
        r = get(self.api + quote(doi), headers=HTTP_HEADERS, timeout=30)
        if r.status_code == 200:
            r.encoding = "utf-8"
            json_res = loads(r.text)
            return json_res.get("message")

    @staticmethod
    def contains(obj, key, value):
        field = None
        if obj:
            field = obj.get(key)
        return field and value in field

    def __get_orcid(self, json_obj):
        result = []
        if json_obj:
            authors = json_obj.get("author")
            if authors:
                for author in authors:
                    orcid = author.get("ORCID")
                    if orcid:
                        orcid = findall("....-....-....-....", orcid)
                        if orcid:
                            result.append(orcid[0])
        return result

    def __get_issn(self, json_obj):
        result = []
        if CrossrefManager.contains(json_obj, "type", "journal"):
            issns = json_obj["ISSN"]
            if issns:
                for issn in issns:
                    norm_issn = sub("\W", "", issn).upper()
                    result.append(norm_issn)
        return result

    def __get_date(self, json_obj):
        if json_obj:
            date = json_obj.get("issued")
            if date:
                date_list = date["date-parts"][0]
                if date_list is not None:
                    l_date_list = len(date_list)
                    if l_date_list != 0 and date_list[0] is not None:
                        if l_date_list == 3 and \
                                ((date_list[1] is not None and date_list[1] != 1) or
                                 (date_list[2] is not None and date_list[2] != 1)):
                            result = datetime(date_list[0], date_list[1], date_list[2], 0, 0).strftime('%Y-%m-%d')
                        elif l_date_list == 2 and date_list[1] is not None:
                            result = datetime(date_list[0], date_list[1], 1, 0, 0).strftime('%Y-%m')
                        else:
                            result = datetime(date_list[0], 1, 1, 0, 0).strftime('%Y')
                        return result

    def get_date(self, doi_entity):
        return self.__get_item(doi_entity, self.date)

    def get_issn(self, doi_entity):
        return self.__get_item(doi_entity, self.issn)

    def get_orcid(self, doi_entity):
        return self.__get_item(doi_entity, self.orcid)

    def __get_item(self, doi_entity, c):
        doi = self.dm.normalize(doi_entity)
        if doi not in c:
            json_obj = self.call_crossref(doi)
            self.issn[doi] = self.__get_issn(json_obj)
            self.date[doi] = self.__get_date(json_obj)
            self.orcid[doi] = self.__get_orcid(json_obj)
        return c.get(doi)

    def share_issn(self, doi_entity_1, doi_entity_2):
        result = False

        doi_entity_1_issns = self.get_issn(doi_entity_1)
        doi_entity_2_issns = self.get_issn(doi_entity_2)
        while not result and doi_entity_1_issns:
            result = doi_entity_1_issns.pop(0) in doi_entity_2_issns

        return result

    def share_orcid(self, doi_entity_1, doi_entity_2):
        result = False

        doi_entity_1_orcid = self.get_orcid(doi_entity_1)
        doi_entity_2_orcid = self.get_orcid(doi_entity_2)
        while not result and doi_entity_1_orcid:
            result = doi_entity_1_orcid.pop(0) in doi_entity_2_orcid

        return result


class ORCIDManager(object):
    def __init__(self, key, m_list=[]):
        self.orcid = {}
        self.api = "https://pub.orcid.org/v2.1/search?q="
        self.dm = DOIManager()
        self.header = {"Content-Type": "application/json"}
        if key:
            self.header["Authorization"] = "Bearer %s" % key
        self.header.update(HTTP_HEADERS)
        self.m_list = m_list

    def call_orcid(self, doi_entity):
        doi = self.dm.normalize(doi_entity)
        r = get(self.api + quote("doi-self:\"%s\" OR doi-self:\"%s\"" % (doi, doi.upper())),
                headers=self.header, timeout=30)
        if r.status_code == 200:
            r.encoding = "utf-8"
            json_res = loads(r.text)
            return json_res.get("result")

    def get_orcid(self, doi_entity):
        doi = self.dm.normalize(doi_entity)
        if doi not in self.orcid:
            json_obj = self.call_orcid(doi)
            result = []
            for item in json_obj:
                orcid = item.get("orcid-identifier")
                if orcid:
                    result.append(orcid["path"])
            self.orcid[doi] = result
        for m in self.m_list:
            if doi in m.orcid:
                for orcid in m.get_orcid(doi):
                    if orcid not in self.orcid[doi]:
                        self.orcid[doi].append(orcid)

        return self.orcid[doi]

    def share_orcid(self, doi_entity_1, doi_entity_2):
        result = False

        doi_entity_1_orcid = self.get_orcid(doi_entity_1)
        doi_entity_2_orcid = self.get_orcid(doi_entity_2)
        while not result and doi_entity_1_orcid:
            result = doi_entity_1_orcid.pop(0) in doi_entity_2_orcid

        return result


class CSVManager(object):
    @staticmethod
    def open_csv(fd_path, metadata=False, delimiter=","):
        result = []

        f_paths = set()
        if exists(fd_path):
            if isdir(fd_path):
                for cur_dir, cur_subdir, cur_files in walk(fd_path):
                    for cur_file in cur_files:
                        if cur_file.endswith(".csv"):
                            f_paths.add(cur_dir + sep + cur_file)
            else:
                if fd_path.endswith(".csv"):
                    f_paths.add(fd_path)

        for f_path in f_paths:
            meta = {}
            with open(f_path) as f:
                cur_citations = list(DictReader(f, delimiter=delimiter))
                if metadata:
                    with open(f_path.replace(".csv", ".json")) as mf:
                        meta = load(mf)
                result.append((cur_citations, meta))

        return result

    @staticmethod
    def list_citations(csv_result):
        result = []
        for citations, metadata in csv_result:
            result.extend(citations)
        return result

    @staticmethod
    def create_set_from_csv(csv_obj, key):
        result = set()

        for row in csv_obj:
            result.add(row[key])

        return result

    @staticmethod
    def store_row(o, t, csv_obj, rdf_graph, is_prov=False):
        d_path = o + sep + "csv" + sep + t[:7].replace("-", sep) + sep
        r_path = o + sep + "rdf" + sep + t[:7].replace("-", sep) + sep

        if is_prov:
            header = ["oci", "agent", "source", "datetime"]
            d_path = d_path.replace(o + sep, o + sep + ".." + sep + "prov" + sep)
            r_path = r_path.replace(o + sep, o + sep + ".." + sep + "prov" + sep)
        else:
            header = ["oci", "citing", "cited", "creation", "timespan", "journal_sc", "author_sc"]

        if not exists(d_path):
            makedirs(d_path)
        if not exists(r_path):
            makedirs(r_path)

        f_path = d_path + t + ".csv"
        f_exists = exists(f_path)
        with open(f_path, "a") as f:
            dw = DictWriter(f, header)
            if not f_exists:
                dw.writeheader()
            dw.writerow(csv_obj)

        t_path = r_path + t + ".ttl"
        with open(t_path, "a") as f:
            rdf_string = Citation.format_rdf(rdf_graph, "nt")
            f.write(rdf_string)


def get_date(doi, d, m_list):
    clean_d = None
    for y, m, d in findall("^([0-9][0-9][0-9][0-9])([0-9][0-9])?([0-9][0-9])?$", sub("[^\d]", "", d)):
        clean_d = y + ("-" + m if m else "") + ("-" + d if d else "")

    while not clean_d and m_list:
        clean_d = m_list.pop(0).get_date(doi)

    return clean_d


if __name__ == "__main__":
    arg_parser = ArgumentParser("cnc.py (Create New Citations",
                                description="This tool allows one to take a four column CSV file describing"
                                            "DOI-to-DOI citations, and to store it according to CSV used by"
                                            "the OpenCitations Indexes so as to be added to CROCI. It uses"
                                            "several online services to check several things to create the"
                                            "final CSV file.")

    arg_parser.add_argument("-i", "--input", required=True, nargs="+",
                            help="The input CSV with new citation data.")
    arg_parser.add_argument("-d", "--data", required=True,
                            help="The directory containing all the CSV files already added in CROCI.")
    arg_parser.add_argument("-o", "--orcid", default=None,
                            help="ORCID API key to be used to query them.")
    arg_parser.add_argument("-l", "--lookup", required=True,
                            help="The lookup table for producing OCIs.")

    args = arg_parser.parse_args()

    print("Retrieve new citation data")
    exi_citations = CSVManager.list_citations(CSVManager.open_csv(args.data))

    print("Retrieve existing citation data")
    exi_ocis = CSVManager.create_set_from_csv(exi_citations, "oci")

    print("Create the DOI Manager")
    doim = DOIManager()

    print("Create the Crossref Manager")
    cm = CrossrefManager()

    print("Create the DataCite Manager")
    dm = DataCiteManager()

    print("Create the ORCID Manager")
    om = ORCIDManager(args.orcid, [cm])

    print("Create the OCI Manager")
    ocim = OCIManager(lookup_file=args.lookup)
    cur_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    citations_already_present = 0
    new_citations_added = 0
    error_in_dois_syntax = 0
    error_in_dois_existence = 0
    all_citations = 0

    for f in args.input:
        try:
            if isdir(f):
                print("\nProcessing files in '%s'" % f)
            else:
                print("\nProcessing file '%s'" % f)
            all_new_citations = CSVManager.open_csv(f, metadata=True)
            for new_citations, new_meta in all_new_citations:
                all_citations += len(new_citations)
                for new_citation in new_citations:
                    citing_doi, cited_doi = \
                        doim.normalize(new_citation["citing_id"]), doim.normalize(new_citation["cited_id"])
                    if citing_doi and cited_doi:
                        oci = ocim.get_oci(citing_doi, cited_doi, "050").replace("oci:", "")
                        if oci not in exi_ocis:
                            exi_ocis.add(oci)
                            if doim.is_valid(citing_doi) and doim.is_valid(cited_doi):
                                print("Create citation data for 'oci:%s' between DOI '%s' and DOI '%s', from '%s'" %
                                      (oci, citing_doi, cited_doi, new_meta["source"]))
                                citing_pub_date, cited_pub_date = \
                                    get_date(citing_doi, new_citation["citing_publication_date"], [cm, dm]), \
                                    get_date(cited_doi, new_citation["cited_publication_date"], [cm, dm])
                                cit = Citation(oci,
                                               BASE_URL + quote(citing_doi), citing_pub_date,
                                               BASE_URL + quote(cited_doi), cited_pub_date,
                                               None, None,
                                               new_meta["agent"], new_meta["source"], cur_time,
                                               "CROCI", "doi", BASE_URL + "([[XXX__decode]])", "reference",
                                               cm.share_issn(citing_doi, cited_doi),
                                               om.share_orcid(citing_doi, cited_doi))

                                # Store in CSV and RDF
                                cit_json = loads(cit.get_citation_json())
                                cit_rdf = cit.get_citation_rdf(CROCI_BASE, False, False, False)
                                cit_json_prov = loads(cit.get_citation_json_prov())
                                cit_rdf_prov = cit.get_citation_prov_rdf(CROCI_BASE)
                                CSVManager.store_row(args.data, cur_time, cit_json, cit_rdf)
                                CSVManager.store_row(args.data, cur_time, cit_json_prov, cit_rdf_prov, True)
                                new_citations_added += 1
                            else:
                                print("WARNING: some DOIs, among '%s' and '%s', do not exist" % (citing_doi, cited_doi))
                                error_in_dois_existence += 1
                        else:
                            print("WARNING: the citation between DOI '%s' and DOI '%s' has been already processed" %
                                  (citing_doi, cited_doi))
                            citations_already_present += 1
                    else:
                        print("WARNING: some DOIs, among '%s' and '%s', is syntactically incorrect" %
                              (citing_doi, cited_doi))
                        error_in_dois_syntax += 1
        except Exception as e:
            print(e.message)

    print("\n# Summary\nNumber of new citations added: %s\nNumber of citations already present in CROCI: %s\nNumber "
          "of citations not added due to a wrong DOI specification: %s (syntax error) and %s (not found "
          "error)\nNumber of citations not processed due to an exception: %s" %
          (new_citations_added, citations_already_present, error_in_dois_syntax, error_in_dois_existence,
           (all_citations -
            (new_citations_added + citations_already_present + error_in_dois_syntax + error_in_dois_existence))))
