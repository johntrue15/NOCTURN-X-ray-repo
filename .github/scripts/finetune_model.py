#!/usr/bin/env python3

import os
import sys
import json
import time
import argparse
import logging
from openai import OpenAI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description='Fine-tune OpenAI models on CT scan data')
    parser.add_argument('--type', choices=['2d', '3d'], required=True, help='Type of model to fine-tune')
    return parser.parse_args()

def validate_files(data_dir):
    """Validate that the training and validation files exist and have enough data"""
    training_file = os.path.join(data_dir, "training.jsonl")
    validation_file = os.path.join(data_dir, "validation.jsonl")
    
    if not os.path.exists(training_file):
        logger.error(f"Training file not found: {training_file}")
        return False
    
    with open(training_file, 'r') as f:
        training_lines = len(f.readlines())
    
    if training_lines < 10:
        logger.error(f"Not enough training examples. Found {training_lines}, need at least 10.")
        return False
    
    if os.path.exists(validation_file):
        with open(validation_file, 'r') as f:
            validation_lines = len(f.readlines())
        logger.info(f"Found {training_lines} training examples and {validation_lines} validation examples.")
    else:
        logger.info(f"Validation file not found: {validation_file}")
        logger.info(f"Will proceed with {training_lines} training examples only.")
    
    return True

def upload_files(client, data_dir):
    """Upload the training and validation files to OpenAI"""
    training_file = os.path.join(data_dir, "training.jsonl")
    validation_file = os.path.join(data_dir, "validation.jsonl")
    
    logger.info(f"Uploading training file: {training_file}")
    with open(training_file, "rb") as f:
        training_response = client.files.create(
            file=f,
            purpose="fine-tune"
        )
    training_file_id = training_response.id
    logger.info(f"Training file uploaded with ID: {training_file_id}")
    
    validation_file_id = None
    if os.path.exists(validation_file):
        logger.info(f"Uploading validation file: {validation_file}")
        with open(validation_file, "rb") as f:
            validation_response = client.files.create(
                file=f,
                purpose="fine-tune"
            )
        validation_file_id = validation_response.id
        logger.info(f"Validation file uploaded with ID: {validation_file_id}")
    
    # Wait for files to be ready
    logger.info("Waiting for files to be processed...")
    
    files_ready = False
    max_retries = 30  # Wait up to 5 minutes (10 seconds × 30)
    retries = 0
    
    while not files_ready and retries < max_retries:
        all_files = client.files.list()
        
        training_ready = any(f.id == training_file_id and f.status == "processed" for f in all_files)
        validation_ready = validation_file_id is None or any(f.id == validation_file_id and f.status == "processed" for f in all_files)
        
        if training_ready and validation_ready:
            files_ready = True
            logger.info("All files are processed and ready for fine-tuning")
            break
        
        logger.info("Files still processing, waiting 10 seconds...")
        time.sleep(10)
        retries += 1
    
    if not files_ready:
        logger.error("Files not processed within the timeout period")
        raise Exception("File processing timeout")
    
    return training_file_id, validation_file_id

def create_fine_tuning_job(client, training_file_id, validation_file_id, model_type):
    """Create a fine-tuning job with OpenAI"""
    # For CT scans, we'll use gpt-4o (which has vision capabilities)
    model_name = "gpt-4o"  
    
    # Create a unique suffix for the model
    suffix = f"ct-{model_type}-{time.strftime('%Y%m%d-%H%M%S')}"
    
    logger.info(f"Creating fine-tuning job with model {model_name} and suffix {suffix}")
    
    job_params = {
        "training_file": training_file_id,
        "model": model_name,
        "suffix": suffix,
    }
    
    if validation_file_id:
        job_params["validation_file"] = validation_file_id
    
    response = client.fine_tuning.jobs.create(**job_params)
    return response

def main():
    args = parse_args()
    model_type = args.type
    data_dir = f"data/finetune/{model_type}"
    
    logger.info(f"Starting fine-tuning for {model_type} model")
    
    # Initialize OpenAI client
    client = OpenAI()
    
    # Validate files
    if not validate_files(data_dir):
        logger.error("File validation failed")
        sys.exit(1)
    
    try:
        # Upload files
        logger.info(f"Uploading files for {model_type} model fine-tuning...")
        training_file_id, validation_file_id = upload_files(client, data_dir)
        
        # Create fine-tuning job
        logger.info(f"Creating fine-tuning job for {model_type} model...")
        job = create_fine_tuning_job(client, training_file_id, validation_file_id, model_type)
        
        # Output job details
        logger.info(f"Fine-tuning job created with ID: {job.id}")
        logger.info(f"Model name will be: {job.model}-{job.suffix}")
        logger.info(f"Job status: {job.status}")
        
        # Save job details to a file for later reference
        job_details = {
            "job_id": job.id,
            "model_type": model_type,
            "base_model": job.model,
            "model_suffix": job.suffix,
            "training_file": training_file_id,
            "validation_file": validation_file_id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": job.status
        }
        
        os.makedirs("data/finetune/jobs", exist_ok=True)
        job_file = f"data/finetune/jobs/{model_type}_{time.strftime('%Y%m%d-%H%M%S')}.json"
        
        with open(job_file, "w") as f:
            json.dump(job_details, f, indent=2)
        
        logger.info(f"Job details saved to {job_file}")
        logger.info("Fine-tuning job submitted successfully")
        
    except Exception as e:
        logger.error(f"Error during fine-tuning process: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 