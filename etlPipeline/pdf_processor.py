from docling.document_converter import DocumentConverter
import os
import json
from multiprocessing import Pool
from typing import Dict, Optional
from datetime import datetime

class PDFProcessor:
    def __init__(self, pdf_sources_file: str, output_path: str, num_cores: int = None):
        """
        Initialize the PDF processor
        
        Args:
            pdf_sources_file: Path to the JSON file containing PDF sources and URLs
            output_path: Path where to save the processed results
            num_cores: Number of CPU cores to use for processing
        """
        self.pdf_sources_file = pdf_sources_file
        self.output_path = output_path
        # Use 75% of available cores by default (18 cores on 24-core system)
        default_cores = max(1, int(os.cpu_count() * 0.75)) if os.cpu_count() else 1
        self.num_cores = num_cores if num_cores else default_cores
        self.converter = DocumentConverter()
        
    def load_pdf_sources(self) -> Dict:
        """Load the PDF sources from the JSON file"""
        try:
            with open(self.pdf_sources_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading PDF sources: {e}")
            return {}

    def process_single_pdf(self, pdf_info: tuple) -> Optional[Dict]:
        """
        Process a single PDF file and extract its contents
        
        Args:
            pdf_info: Tuple of (filepath, source_info)
            
        Returns:
            Dictionary containing processed PDF data or None if processing failed
        """
        filepath, source_info = pdf_info
        try:
            # Convert the PDF
            result = self.converter.convert(filepath)
            filename = os.path.basename(filepath)
            
            # Extract text and sections
            full_texts = [text.text for text in result.document.texts]
            
            # Process sections
            sections = []
            current_section = {'header': '', 'content': []}
            for text in result.document.texts:
                if 'section_header' in str(text.label).lower():
                    if current_section['header']:
                        sections.append(current_section.copy())
                    current_section = {'header': text.text, 'content': []}
                else:
                    current_section['content'].append(text.text)
            
            if current_section['header']:
                sections.append(current_section)
            
            # Combine all information
            processed_data = {
                'filepath': filepath,
                'source_url': source_info['source_url'],
                'pdf_url': source_info['pdf_url'],
                'content': {
                    'full_text': ' '.join(full_texts),  # Combined for easier processing
                    'sections': sections,
                    'raw_texts': full_texts  # Original separate text blocks
                },
                'metadata': {
                    'filename': filename,
                    'doc_metadata': {
                        'schema_name': result.document.schema_name,
                        'version': result.document.version,
                        'name': result.document.name,
                        'origin': {
                            'mimetype': result.document.origin.mimetype,
                            'filename': result.document.origin.filename
                        }
                    },
                    'processing_time': datetime.now().isoformat(),
                    'word_count': len(' '.join(full_texts).split()),
                    'section_count': len(sections)
                }
            }
            
            print(f"Successfully processed: {filename}")
            return processed_data
            
        except Exception as e:
            print(f"Error processing {filepath}: {str(e)}")
            return None

    def process_all_pdfs(self) -> None:
        """Process all PDFs and save results to a JSON file"""
        # Load PDF sources
        pdf_sources = self.load_pdf_sources()
        if not pdf_sources:
            print("No PDF sources found. Please run pdf_downloader.py first.")
            return

        # Prepare input for multiprocessing
        pdf_items = list(pdf_sources.items())
        
        # Process PDFs in parallel
        with Pool(processes=self.num_cores) as pool:
            results = pool.map(self.process_single_pdf, pdf_items)
        
        # Filter out None results and organize by filepath
        processed_pdfs = {
            result['filepath']: result
            for result in results
            if result is not None
        }
        
        # Save results
        try:
            output_data = {
                'metadata': {
                    'total_pdfs': len(processed_pdfs),
                    'processing_time': datetime.now().isoformat(),
                    'success_rate': f"{len(processed_pdfs)}/{len(pdf_sources)}"
                },
                'processed_pdfs': processed_pdfs
            }
            
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            print(f"\nResults successfully saved to: {self.output_path}")
            
        except Exception as e:
            print(f"Error saving results: {str(e)}")

if __name__ == "__main__":
    # Define paths relative to script location
    current_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_sources_file = os.path.join(current_dir, "pdf_sources.json")
    output_file = os.path.join(current_dir, "processed_pdfs.json")
    
    # Create processor instance and run
    processor = PDFProcessor(pdf_sources_file, output_file)
    processor.process_all_pdfs()
