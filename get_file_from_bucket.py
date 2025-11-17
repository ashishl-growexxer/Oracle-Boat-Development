
import oci
import csv

from inference_code import OCIModel
from pdf2image import convert_from_path
from typing import Optional, List, Dict, Any
from io import BytesIO
from PIL import Image
import io, base64
import json
import os
import pandas as pd
from extract_headers_and_lines import extract_po_from_file



def extract_values_only(data, prefix=""):
    flat = {}
    for key, val in data.items():
        new_key = f"{prefix}.{key}" if prefix else key

        # Typical structure: {"value": "...", "coordinates": [...]}
        if isinstance(val, dict) and "value" in val:
            flat[new_key] = val.get("value", "")
            continue

        # Nested objects → recursive flatten
        if isinstance(val, dict):
            flat.update(extract_values_only(val, new_key))
        else:
            # simple values (string, list, etc.)
            flat[new_key] = val

    return flat


def bucket(filename):
    filename = filename + '.pdf'
    config = oci.config.from_file("config.ini")
    object_storage_client = oci.object_storage.ObjectStorageClient(config)

    get_object_response = object_storage_client.get_object(
        bucket_name="BOAT-BUCKET",
        namespace_name="bmb8tbvmgtsy",
        object_name = f"pdf/{filename}"
        )

    # Get the data from response
    with open(filename, "wb") as f:
        for chunk in get_object_response.data.raw.stream(1024 * 1024, decode_content=False):
            f.write(chunk)


    model = OCIModel(
        model_id="ocid1.generativeaimodel.oc1.us-chicago-1.amaaaaaask7dceyayjawvuonfkw2ua4bob4rlnnlhs522pafbglivtwlfzta",
        compartment_id="ocid1.compartment.oc1..aaaaaaaa7wyo7euk2wfekpv36obtfbqgupxeb5yylivifscxseudvwwp2ixa",
        config_profile="DEFAULT"
    )

    # Example 2: Inference with PIL Images (like BedrockModel.infer_with_images())
    print("=" * 60)
    print("Bucket object downloaded and model initiated, Now we infer")
    print("=" * 60)

    images = convert_from_path(filename, dpi=200)

    with open("prompts/new_prompt.txt", "r", encoding="utf-8") as file:
        file_contents = file.read()

    response = model.infer_with_images(
        images=images,
        prompt=file_contents
    )
    print('*'*100)
    print(type(response))

    output_file = "response_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(str(response))

    if os.path.exists(filename):
        os.remove(filename)
        print(f"{filename} deleted successfully.")
    else:
        print("File not found.")

    header_df  ,lineitems_df = extract_po_from_file(file_path='response_output.txt')
    return header_df, lineitems_df
    


