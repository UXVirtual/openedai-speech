#!/bin/sh
# -----------------------------------------------
#  MANDATORY: Replace with your information
# -----------------------------------------------
repo_id="rhasspy/piper-voices"  # Repository ID of the model on Hugging Face
folder_name="en/en_GB/vctk/medium/samples"                  # Name of the folder within the repository
download_dir="$PWD/voices/vctk"    # Where you want to download the folder 

# -----------------------------------------------
# Download the folder
# -----------------------------------------------
mkdir -p "$download_dir"  # Ensure the download directory exists
# Use git clone for folder-level download
temp_dir=$(mktemp -d)  # Create a temporary directory
git clone --depth 1 --filter=blob:none --sparse https://huggingface.co/$repo_id $temp_dir  # Shallow clone for efficiency
cd $temp_dir 
git sparse-checkout set $folder_name 
mv $temp_dir/$folder_name/* $download_dir
rm -rf $temp_dir  # Clean up the temporary directory