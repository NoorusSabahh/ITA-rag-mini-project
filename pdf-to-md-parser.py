!pip install llama-cloud-services llama-index-core llama-index-readers-file nest_asyncio --quiet

import os
import nest_asyncio
from llama_cloud_services import LlamaParse
from llama_index.core import SimpleDirectoryReader

# Allow async operations to run in Jupyter/Colab
nest_asyncio.apply()

os.environ["LLAMA_CLOUD_API_KEY"] = "your_api_key_here"  # Replace this with your actual Llama Cloud key

parser = LlamaParse(result_type="markdown")
file_extractor = {".pdf": parser}

pdf_folder = "/content"  # Replace with path to your PDF folder
output_folder = "markdowns"
os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(pdf_folder):
    if filename.lower().endswith(".pdf"):
        pdf_path = os.path.join(pdf_folder, filename)
        print(f"Parsing: {pdf_path}")
        try:
            documents = SimpleDirectoryReader(
                input_files=[pdf_path],
                file_extractor=file_extractor
            ).load_data()

            combined_text = "\n\n".join(doc.text for doc in documents)

            markdown_filename = os.path.splitext(filename)[0] + ".md"
            output_path = os.path.join(output_folder, markdown_filename)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(combined_text)

            print(f"Saved markdown for '{filename}' to '{output_path}'.")

        except Exception as e:
            print(f"Failed to load file {pdf_path} with error: {e}")
