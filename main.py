import oci
import configparser
import os
from get_file_from_bucket import bucket
import time

def initialize_client():
    """Initialize OCI client by reading config"""
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    oci_config = {
        "user": config['DEFAULT']['user'],
        "key_file": config['DEFAULT']['key_file'],
        "fingerprint": config['DEFAULT']['fingerprint'],
        "tenancy": config['DEFAULT']['tenancy'],
        "region": config['DEFAULT']['region']
    }
    
    bucket_info = {
        "namespace": "bmb8tbvmgtsy",
        "bucket_name": "BOAT-BUCKET",
        "compartment_id": "ocid1.compartment.oc1..aaaaaaaa7wyo7euk2wfekpv36obtfbqgupxeb5yylivifscxseudvwwp2ixa",
        "region": config['DEFAULT']['region']
    }
    
    client = oci.object_storage.ObjectStorageClient(oci_config)
    return client, bucket_info

def get_pdf_files_from_bucket():
    """Get all PDF file names and URLs from pdf folder in bucket"""
    print("Get file names from bucket")
    client, bucket_info = initialize_client()
    
    namespace = bucket_info['namespace']
    bucket_name = bucket_info['bucket_name']
    
    # List objects in pdf folder
    response = client.list_objects(
        namespace_name=namespace,
        bucket_name=bucket_name,
        prefix="pdf/"
    )
    
    file_names = []
    file_urls = []
    
    for obj in response.data.objects:
        file_name = obj.name
        
        # Skip if it's just the folder name "pdf/"
        if file_name == "pdf/" or file_name.endswith("/"):
            continue
        
        # Remove "pdf/" prefix
        if file_name.startswith("pdf/"):
            file_name = file_name[4:]
        
        # Remove ".pdf" extension
        if file_name.endswith(".pdf"):
            file_name = file_name[:-4]
        
        file_names.append(file_name)
        
        # Generate URL with original object name
        original_obj_name = obj.name
        url = f"https://objectstorage.{bucket_info['region']}.oraclecloud.com/n/{namespace}/b/{bucket_name}/o/{original_obj_name}"
        file_urls.append(url)
    
    print("Filenames fetched successfully")
    return file_names, file_urls

def upload_file_to_csv_folder(filename):
    """Upload file to csv folder in bucket"""
    print(f"uplaoding file {filename}")
    client, bucket_info = initialize_client()
    
    # Read file from local directory
    with open(filename, 'rb') as f:
        file_content = f.read()
    
    # Get just the filename from path
    actual_filename = os.path.basename(filename)
    object_name = f"csv/{actual_filename}"
    
    response = client.put_object(
        namespace_name=bucket_info['namespace'],
        bucket_name=bucket_info['bucket_name'],
        object_name=object_name,
        put_object_body=file_content,
        content_type="text/csv"
    )
    print(f"Uploading process finished {response}")
    
    return object_name

def main_logic(filename):
    print(f"Processing file: {filename}")
    header_df, lines_df = bucket(filename)
    print(header_df.head())
    header_csv_file = filename + '_headers_' + '.csv'
    lines_csv_file = filename + '_lines_' + '.csv'
    header_df.to_csv(header_csv_file)
    lines_df.to_csv(lines_csv_file)

    upload_file_to_csv_folder(lines_csv_file)
    upload_file_to_csv_folder(header_csv_file)

    if os.path.exists(header_csv_file):
        os.remove(header_csv_file)
        print(f"{header_csv_file} file deleted successfully.")
    else:
        print(f"Failed to delete {header_csv_file}.")

    if os.path.exists(lines_csv_file):
        os.remove(lines_csv_file)
        print(f"{lines_csv_file} file deleted successfully.")
    else:
        print(f"Failed to delete {lines_csv_file}.")
    
