"""

Converter for the Icelandic Gigaword Corpus (IGC) TEI-XML format,
producing one JSON object per document with the full text and
sentence/paragraph offsets.

This file, along with the accompanying subcorpora_categorization.tsv,
originates from the "Icelandic Gigaword Corpus JSONL Converter", a
published resource available from CLARIN:

    https://repository.clarin.is/repository/xmlui/handle/20.500.12537/336

developed with funding from the Icelandic government initiative
"Language Technology for Icelandic 2019-2023". Refer to the CLARIN
page for licensing and citation information.

The copy here differs from the published version in one respect:
get_doc_data() computes the length of every sentence after the first
in a paragraph as len(sentence) - 1 rather than len(sentence) - 2,
since split_into_sentences(..., original=True) leaves only one leading
space to trim. The published version silently clipped the final
character (usually the trailing period) of those sentences.

"""

import json
import os
import xml.etree.ElementTree as ET
import uuid
from tokenizer import split_into_sentences
from datetime import date

# Path to the TSV file containing information on the corpora
INFO_MAP_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "subcorpora_categorization.tsv")

# XML namespaces
XML_NAMESPACE = "{http://www.tei-c.org/ns/1.0}"
XML_ID_NAMESPACE = "{http://www.w3.org/XML/1998/namespace}"

# Paragraph and title types for each subcorpus
PARAGRAPH_TYPES = {
    "Adjud": 1,
    "Books": 1,
    "Journals": 1,
    "Law": 1,
    "News1": 1,
    "News2": 1,
    "Parla": 2,
    "Social": 1,
    "Wiki": 1,
}
TITLE_TYPES = {
    "Adjud": 1,
    "Books": 1,
    "Journals": 1,
    "Law": 2,
    "News1": 1,
    "News2": 1,
    "Parla": 3,
    "Social": 1,
    "Wiki": 1,
}


class XMLToJsonlConverter:
    """Convert XML files to JSONL format."""

    def __init__(self, corpus: str, input_path: str, output_path: str) -> None:
        self.corpus = corpus
        self.input_path = input_path
        self.output_path = output_path

    def get_info_map(self) -> dict:
        """Get the information map for all listed corpora."""

        # Read the tsv file containing information on the corpora
        with open(INFO_MAP_FILE, "r") as f:
            info_map = {}
            # Skip the header in the file
            next(f)
            for line in f:
                info = line.split("\t")
                corpus_name = info[0].split(".tsv")[0]
                domain = info[1].lower()
                if "–" in domain:
                    domain = [d.strip() for d in domain.split("–")]
                else:
                    domain = [domain]
                lang = "is"
                quality = info[-1].strip()
                info_map[corpus_name] = {
                    "domain": domain,
                    "lang": lang,
                    "quality": quality,
                }

            return info_map

    def get_paragraphs(self, paragraphs: ET, type) -> list:
        """Get the text from the paragraphs in the XML file."""

        clean_paragraphs = []
        for section in paragraphs:
            for paragraph in section:
                if type == 1:
                    text = paragraph.text
                    if text != "" and text is not None:
                        # Each paragraph is a single string in the clean_paragraphs list
                        clean_paragraphs.append(text)
                elif type == 2:
                    # This only applies to parliamentary data, where each paragraph is a speech from one speaker
                    paragraph_text = []
                    for segment in paragraph:
                        text = segment.text
                        if text != "" and text is not None:
                            # Each segment is a part of the paragraph
                            paragraph_text.append(text)
                    # Each paragraph is a single string in the clean_paragraphs list
                    clean_paragraphs.append(" ".join(paragraph_text))

        return clean_paragraphs

    def get_title(self, title_list: list, title_type: int) -> tuple:
        """Get the title information from the XML file."""

        if len(title_list) != 0:
            if title_type == 1:
                title = title_list[0].text
            elif title_type == 2:
                titles = []
                for t in title_list:
                    if t.attrib[f"{XML_ID_NAMESPACE}lang"] == "is":
                        if t.attrib["type"] == "main":
                            titles.append(t.text)
                        if t.attrib["type"] == "sub":
                            titles.append(t.text)
                        title = t.text
                # Join the two titles together so that they belong to the same paragraph
                title = " ".join(titles)
            elif title_type == 3:
                title = [
                    t for t in title_list if t.attrib[f"{XML_ID_NAMESPACE}lang"] == "is"
                ][0].text
            title_info = (0, len(title))
        else:
            title_info = (None, None)

        return title, title_info

    def get_doc_data(
        self, paragraphs: ET, title_list: list, paragraph_type: int, title_type: int
    ) -> tuple:
        """Get the text, paragraph information, sentence information and title information from the XML file."""

        # Get all paragraphs in the XML file
        clean_paragraphs = self.get_paragraphs(paragraphs, paragraph_type)

        title, title_info = self.get_title(title_list, title_type)

        # Add the title as the first element in paragraphs
        clean_paragraphs.insert(0, title)

        # Get the length of each paragraph
        paragraph_lens = [len(p) for p in clean_paragraphs]

        combined_paragraphs = "\n\n".join([p for p in clean_paragraphs])

        # Get the offset and length of each paragraph
        paragraph_offsets = []
        paragraph_len = 0
        for i in range(len(combined_paragraphs)):
            if i == 0:
                paragraph_len = 0
                paragraph_offsets.append(paragraph_len)
            elif combined_paragraphs[i] == "\n" and combined_paragraphs[i + 1] == "\n":
                paragraph_len = i + 2
                paragraph_offsets.append(paragraph_len)

        # Get the offset and length of each sentence
        sentence_offsets = []
        sentence_lens = []
        paragraph_len = 0
        for p in clean_paragraphs:
            sentences = list(split_into_sentences(p, original=True))
            sentence_len = 0
            for i, sentence in enumerate(sentences):
                if i == 0:
                    sentence_offsets.append(paragraph_len)
                    sentence_lens.append(len(sentence))
                else:
                    sentence_offsets.append(
                        paragraph_len + sum([len(s) for s in sentences[:i]]) + 1
                    )
                    # split_into_sentences(..., original=True) keeps a single
                    # leading space on every sentence after the first (see
                    # sentence_offsets' "+ 1" above, which skips past it) --
                    # so only that one leading character needs trimming from
                    # the length here, not two. The previous "- 2" clipped an
                    # extra character off the end, silently dropping the
                    # sentence's own trailing period/punctuation.
                    sentence_lens.append(len(sentence) - 1)
                sentence_len += len(sentence) + 1
            paragraph_len += len(p) + 2

        all_paragraph_info = zip(paragraph_offsets, paragraph_lens)
        all_sentence_info = zip(sentence_offsets, sentence_lens)

        return combined_paragraphs, all_paragraph_info, all_sentence_info, title_info

    def create_dict_obj(
        self,
        document: str,
        uuid: str,
        author: list,
        fetch_timestamp: str,
        xml_id: str,
        publish_timestamp: list,
        title_info: tuple,
        paragraphs: zip,
        sentences: zip,
        source: list,
    ) -> dict:
        """Create a dictionary object for a single XML file."""

        doc_object = {}
        doc_object["document"] = document
        doc_object["uuid"] = uuid

        metadata = {}
        metadata["author"] = author[0].text if len(author) != 0 else None
        metadata["fetch_timestamp"] = fetch_timestamp
        metadata["xml_id"] = xml_id
        metadata["publish_timestamp"] = (
            publish_timestamp[0].text if len(publish_timestamp) != 0 else None
        )
        metadata["title"] = (
            {"offset": title_info[0], "length": title_info[1]}
            if title_info[0] is not None
            else None
        )
        metadata["paragraphs"] = [{"offset": p[0], "length": p[1]} for p in paragraphs]
        metadata["sentences"] = [{"offset": s[0], "length": s[1]} for s in sentences]
        metadata["source"] = source[0].text if len(source) != 0 else None
        doc_object["metadata"] = metadata

        return doc_object

    def convert_to_jsonl(self, input_file: str) -> dict:
        """Convert an XML file to JSONL format."""

        with open(input_file, "r") as f:
            tree = ET.parse(f)
            root = tree.getroot()
            xml_id = root.attrib.get(f"{XML_ID_NAMESPACE}id")
            header = root[0]
            file_desc = header[0]

            source_desc = [
                el for el in file_desc if el.tag == f"{XML_NAMESPACE}sourceDesc"
            ][0]
            # There are two structures to sourceDesc and we need to account for both
            bibl = source_desc.findall(f"{XML_NAMESPACE}biblStruct")
            if len(bibl) == 0:
                bibl = source_desc.findall(f"{XML_NAMESPACE}bibl")
                for el in bibl:
                    title = el.findall(f"{XML_NAMESPACE}title")
                    author = el.findall(f"{XML_NAMESPACE}author")
                    source = el.findall(f"{XML_NAMESPACE}idno")
                    publish_timestamp = el.findall(f"{XML_NAMESPACE}date")
            else:
                bibl_info = bibl[0].findall(f"{XML_NAMESPACE}analytic")

                if len(bibl_info) == 0:
                    for el in bibl[0].findall(f"{XML_NAMESPACE}monogr"):

                        title = el.findall(f"{XML_NAMESPACE}title")
                        author = el.findall(f"{XML_NAMESPACE}author")
                        source = el.findall(f"{XML_NAMESPACE}idno")
                        publish_timestamp = el.findall(f"{XML_NAMESPACE}date")

                    if len(publish_timestamp) == 0:

                        for imprint in el.findall(f"{XML_NAMESPACE}imprint"):
                            publish_timestamp = imprint.findall(f"{XML_NAMESPACE}date")

                else:
                    for el in bibl_info:
                        title = el.findall(f"{XML_NAMESPACE}title")
                        author = el.findall(f"{XML_NAMESPACE}author")
                        source = el.findall(f"{XML_NAMESPACE}idno")
                        publish_timestamp = el.findall(f"{XML_NAMESPACE}date")

                    if len(publish_timestamp) == 0:

                        for monogr in bibl[0].findall(f"{XML_NAMESPACE}monogr"):

                            for el in monogr.findall(f"{XML_NAMESPACE}imprint"):
                                publish_timestamp = el.findall(f"{XML_NAMESPACE}date")

            fetch_timestamp = date.today().strftime("%Y-%m-%d")
            gen_uuid = str(uuid.uuid4())
            text = root[1]
            paragraphs = text[0]
            paragraph_type = PARAGRAPH_TYPES[self.corpus]
            title_type = TITLE_TYPES[self.corpus]
            document, paragraphs, sentences, title_info = self.get_doc_data(
                paragraphs, title, paragraph_type, title_type
            )
            doc_object = self.create_dict_obj(
                document,
                gen_uuid,
                author,
                fetch_timestamp,
                xml_id,
                publish_timestamp,
                title_info,
                paragraphs,
                sentences,
                source,
            )

            return doc_object

    def get_corpus_info(
        self, corpus_name: str, output_name: str, info_map: dict
    ) -> dict:
        """Get information on the corpus."""

        updated_corpus_name = corpus_name
        # Corpus names in info_map are sometimes slightly different from the actual corpus names
        if corpus_name not in info_map:
            if corpus_name == "IGC-Adjud-Appeal":
                updated_corpus_name = "IGC-Adjud2"
            elif corpus_name == "IGC-Adjud-District":
                updated_corpus_name = "IGC-Adjud1"
            elif corpus_name == "IGC-Adjud-Supreme":
                updated_corpus_name = "IGC-Adjud3"
            elif corpus_name == "IGC-Law-Bills":
                updated_corpus_name = "IGC-Law2"
            elif corpus_name == "IGC-Law-Law":
                updated_corpus_name = "IGC-Law3"
            elif corpus_name == "IGC-Law-Proposals":
                updated_corpus_name = "IGC-Law1"
            elif corpus_name == "IGC-News1-frettabladid_is":
                updated_corpus_name = "IGC-News1-frettabladidis"
            elif corpus_name == "IGC-News1-ras1_og_2":
                updated_corpus_name = "IGC-News1-ras1og2"
            elif corpus_name == "IGC-News2-dv_is":
                updated_corpus_name = "IGC-News2-dvis"
            elif corpus_name == "IGC-News2-frettatiminn_bl":
                updated_corpus_name = "IGC-News2-frettatiminnbl"
            elif corpus_name == "IGC-News2-kjarninn_blad":
                updated_corpus_name = "IGC-News2-kjarninnblad"
            elif corpus_name == "IGC-News2-stundin_blad":
                updated_corpus_name = "IGC-News2-stundinblad"
            elif corpus_name == "IGC-News2-stundin_serblad":
                updated_corpus_name = "IGC-News2-stundinserblad"
            elif corpus_name == "IGC-Social-Blog-heimur":
                updated_corpus_name = "IGC-Social2-heimur"
            elif corpus_name == "IGC-Social-Blog-jonas":
                updated_corpus_name = "IGC-Social2-jonas"
            elif corpus_name == "IGC-Social-Blog-silfuregils":
                updated_corpus_name = "IGC-Social2-silfuregils"
            elif corpus_name == "IGC-Social-Forums-bland":
                updated_corpus_name = "IGC-Social1-bland"
            elif corpus_name == "IGC-Social-Forums-hugi":
                updated_corpus_name = "IGC-Social1-hugi"
            elif corpus_name == "IGC-Social-Forums-malefnin":
                updated_corpus_name = "IGC-Social1-malefnin"

        output_directory = os.path.join(
            self.output_path, "converted-corpora", f"IGC-{self.corpus}"
        )

        corpus_info = {
            f"{corpus_name}": {
                "path": os.path.join(os.path.abspath(output_directory), output_name),
                "quality": info_map[updated_corpus_name]["quality"],
                "domain": info_map[updated_corpus_name]["domain"],
                "lang": info_map[updated_corpus_name]["lang"],
                "version": self.input_path.split("/")[-2]
                .split("-")[-1]
                .rsplit(".", 1)[0],
            }
        }

        return corpus_info

    def write_to_jsonl(self, output_name: str, combined_files: list) -> None:
        """Write the converted corpus to a single file."""

        output_directory = os.path.join(
            self.output_path, "converted-corpora", f"IGC-{self.corpus}"
        )
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        with open(
            os.path.join(output_directory, output_name),
            "w",
        ) as output:
            print("Writing to:", os.path.join(output_directory, output_name))
            for doc in combined_files:
                json.dump(doc, output, ensure_ascii=False)
                output.write("\n")

    def write_dataset_info(self, datasets_info: list) -> None:
        """Write the dataset information to a file."""

        output_directory = os.path.join(self.output_path, "datasets-info")
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        output_file = os.path.join(output_directory, f"IGC-{self.corpus}.jsonl")

        print("Writing dataset information to:", output_file)

        with open(
            output_file,
            "w",
        ) as datasets_output:
            for line in datasets_info:
                json.dump(line, datasets_output, ensure_ascii=False)
                datasets_output.write("\n")

    def create_jsonl_type1(self) -> None:
        """Convert all XML files, which are of type 1, in the input path to JSONL format and write the output to a file."""

        datasets_info = []
        info_map = self.get_info_map()

        # Compile all data
        for subcorpus in sorted(os.listdir(self.input_path)):
            if os.path.isdir(os.path.join(self.input_path, subcorpus)):
                subcorpus_name = f"IGC-{self.corpus}-{subcorpus}"
                output_name = f"{subcorpus_name}.jsonl"
                subcorpus_info = self.get_corpus_info(
                    subcorpus_name, output_name, info_map
                )
                datasets_info.append(subcorpus_info)

                combined_files = []

                print("Converting files for:", output_name)

                for year in sorted(
                    os.listdir(os.path.join(self.input_path, subcorpus))
                ):
                    if os.path.isdir(os.path.join(self.input_path, subcorpus, year)):
                        for file in sorted(
                            os.listdir(os.path.join(self.input_path, subcorpus, year))
                        ):
                            input_file = os.path.join(
                                self.input_path, subcorpus, year, file
                            )
                            converted_file = self.convert_to_jsonl(input_file)
                            combined_files.append(converted_file)

                # Write the converted output to a file
                self.write_to_jsonl(output_name, combined_files)

        # Write dataset info to a file
        self.write_dataset_info(datasets_info)

    def create_jsonl_type2(self) -> None:
        """Convert all XML files, which are of type 2, in the input path to JSONL format and write the output to a file."""

        datasets_info = []
        info_map = self.get_info_map()

        corpus_name = f"IGC-{self.corpus}"
        output_name = f"{corpus_name}.jsonl"
        corpus_info = self.get_corpus_info(corpus_name, output_name, info_map)
        datasets_info.append(corpus_info)

        combined_files = []

        print("Converting files for:", output_name)

        # Compile all data
        for year in sorted(os.listdir(self.input_path)):
            if os.path.isdir(os.path.join(self.input_path, year)):
                for file in sorted(os.listdir(os.path.join(self.input_path, year))):
                    input_file = os.path.join(self.input_path, year, file)
                    converted_file = self.convert_to_jsonl(input_file)
                    combined_files.append(converted_file)

        # Write the output to a file
        self.write_to_jsonl(output_name, combined_files)

        # Write dataset info to a file
        self.write_dataset_info(datasets_info)

    def create_jsonl_type3(self) -> None:
        """Convert all XML files, which are of type 3, in the input path to JSONL format and write the output to a file."""

        datasets_info = []
        info_map = self.get_info_map()

        # Compile all data
        for subcorpus in sorted(os.listdir(self.input_path)):
            if os.path.isdir(os.path.join(self.input_path, subcorpus)):
                subcorpus_name = f"IGC-{self.corpus}-{subcorpus}"
                output_name = f"{subcorpus_name}.jsonl"
                subcorpus_info = self.get_corpus_info(
                    subcorpus_name, output_name, info_map
                )
                datasets_info.append(subcorpus_info)

                combined_files = []

                print("Converting files for:", output_name)

                for year in sorted(
                    os.listdir(os.path.join(self.input_path, subcorpus))
                ):
                    if os.path.isdir(os.path.join(self.input_path, subcorpus, year)):
                        for number in sorted(
                            os.listdir(os.path.join(self.input_path, subcorpus, year))
                        ):
                            if os.path.isdir(
                                os.path.join(self.input_path, subcorpus, year, number)
                            ):
                                for file in sorted(
                                    os.listdir(
                                        os.path.join(
                                            self.input_path, subcorpus, year, number
                                        )
                                    )
                                ):
                                    input_file = os.path.join(
                                        self.input_path,
                                        subcorpus,
                                        year,
                                        number,
                                        file,
                                    )
                                    converted_file = self.convert_to_jsonl(input_file)
                                    combined_files.append(converted_file)

                # Write the output to a file
                self.write_to_jsonl(output_name, combined_files)

        # Write dataset info to a file
        self.write_dataset_info(datasets_info)

    def create_jsonl_type4(self) -> None:
        """Convert all XML files, which are of type 4, in the input path to JSONL format and write the output to a file."""

        datasets_info = []
        info_map = self.get_info_map()

        # Compile all data
        for type in sorted(os.listdir(self.input_path)):
            if (
                os.path.isdir(os.path.join(self.input_path, type)) and type != "Twitter"
            ):  # Twitter data is empty, so we don't include that in the conversion
                for subcorpus in sorted(
                    os.listdir(os.path.join(self.input_path, type))
                ):
                    if os.path.isdir(os.path.join(self.input_path, type, subcorpus)):

                        subcorpus_name = f"IGC-{self.corpus}-{type}-{subcorpus}"
                        output_name = f"{subcorpus_name}.jsonl"
                        subcorpus_info = self.get_corpus_info(
                            subcorpus_name, output_name, info_map
                        )
                        datasets_info.append(subcorpus_info)

                        combined_files = []

                        print("Converting files for:", output_name)

                        for year in sorted(
                            os.listdir(os.path.join(self.input_path, type, subcorpus))
                        ):
                            if os.path.isdir(
                                os.path.join(self.input_path, type, subcorpus, year)
                            ):
                                for file in sorted(
                                    os.listdir(
                                        os.path.join(
                                            self.input_path, type, subcorpus, year
                                        )
                                    )
                                ):
                                    input_file = os.path.join(
                                        self.input_path, type, subcorpus, year, file
                                    )
                                    converted_file = self.convert_to_jsonl(input_file)
                                    combined_files.append(converted_file)

                        # Write the output to a file
                        self.write_to_jsonl(output_name, combined_files)

        # Write dataset info to a file
        self.write_dataset_info(datasets_info)

    def create_jsonl(self, corpus_type):
        """Convert the XML files in the input path to JSONL format based on the corpus type."""

        if corpus_type == 1:
            self.create_jsonl_type1()
        elif corpus_type == 2:
            self.create_jsonl_type2()
        elif corpus_type == 3:
            self.create_jsonl_type3()
        elif corpus_type == 4:
            self.create_jsonl_type4()
