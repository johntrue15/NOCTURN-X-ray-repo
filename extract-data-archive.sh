#!/bin/bash
# Script to extract the compressed historical data archive

if [ ! -f "data_archive.tar.gz" ]; then
    echo "Error: data_archive.tar.gz not found"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p data

echo "Extracting historical data from data_archive.tar.gz..."
tar -xzf data_archive.tar.gz -C /tmp/

# Move extracted directories to data/
if [ -d "/tmp/old_data" ]; then
    mv /tmp/old_data/* data/
    rm -rf /tmp/old_data
    echo "Extraction complete!"
    echo "Historical data restored to: $(pwd)/data/"
    echo ""
    echo "Data directories now available:"
    ls -1 data/ | head -10
    if [ $(ls -1 data/ | wc -l) -gt 10 ]; then
        echo "... and $(($(ls -1 data/ | wc -l) - 10)) more"
    fi
else
    echo "Error: Extraction failed"
    exit 1
fi
