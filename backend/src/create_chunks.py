from langchain_text_splitters import TokenTextSplitter
from langchain.docstore.document import Document
from langchain_neo4j import Neo4jGraph
import logging
from src.document_sources.youtube import get_chunks_with_timestamps, get_calculated_timestamps
import re
import os

logging.basicConfig(format="%(asctime)s - %(message)s", level="INFO")


class CreateChunksofDocument:
    def __init__(self, pages: list[Document], graph: Neo4jGraph):
        self.pages = pages
        self.graph = graph

    def split_file_into_chunks(self,token_chunk_size, chunk_overlap):
        """
        Split a list of documents(file pages) into chunks of fixed size.

        Args:
            pages: A list of pages to split. Each page is a list of text strings.

        Returns:
            A list of chunks each of which is a langchain Document.
        """
        logging.info("Split file into smaller chunks")
        logging.info(f"MYYYYY CHUNK_SIZE: {token_chunk_size}")
        logging.info(f"MYYYYY CHUNK_OVERLAP: {chunk_overlap}")
        text_splitter = TokenTextSplitter(chunk_size=token_chunk_size, chunk_overlap=chunk_overlap)
        MAX_TOKEN_CHUNK_SIZE = 5242880 #int(os.getenv('MAX_TOKEN_CHUNK_SIZE', 10000))
        logging.info("MAX_TOKEN_CHUNK_SIZE: %s", MAX_TOKEN_CHUNK_SIZE)
        chunk_to_be_created = int(MAX_TOKEN_CHUNK_SIZE / token_chunk_size)
        logging.info("# NUMBER OF CHUNKS: %s", chunk_to_be_created)
        
        if 'page' in self.pages[0].metadata:
            chunks = []
            for i, document in enumerate(self.pages):
                page_number = i + 1
                # DON'T LIMIT THE CHUNKS
                # if len(chunks) >= chunk_to_be_created:
                #     break
                # else:
                for chunk in text_splitter.split_documents([document]):
                    chunks.append(Document(page_content=chunk.page_content, metadata={'page_number':page_number}))    
                    # MODIFIED
                    # all_metadata = {'page_number':page_number, **self.pages[0].metadata}
                    # logging.info(f"Creating chunk for page {page_number} with metadata: {all_metadata}")
                    # chunks.append(Document(page_content=chunk.page_content, metadata=all_metadata))
        elif 'length' in self.pages[0].metadata:
            if len(self.pages) == 1  or (len(self.pages) > 1 and self.pages[1].page_content.strip() == ''): 
                match = re.search(r'(?:v=)([0-9A-Za-z_-]{11})\s*',self.pages[0].metadata['source'])
                youtube_id=match.group(1)   
                chunks_without_time_range = text_splitter.split_documents([self.pages[0]])
                chunks = get_calculated_timestamps(chunks_without_time_range[:chunk_to_be_created], youtube_id)
            else: 
                chunks_without_time_range = text_splitter.split_documents(self.pages)
                chunks = get_chunks_with_timestamps(chunks_without_time_range[:chunk_to_be_created])
        else:
            chunks = text_splitter.split_documents(self.pages)
        
        # DON'T LIMIT THE CHUNKS
        # chunks = chunks[:chunk_to_be_created]
        logging.info(f"Total number of chunks created: {len(chunks)}")
        return chunks