import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import argparse
import logging

def setup_logging(log_file):
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def load_parquet_data(parquet_file):
    """Load data from parquet file"""
    return pd.read_parquet(parquet_file)

def create_graphs(df, output_dir, logger):
    """Create various graphs from the parquet data"""
    # Set style
    plt.style.use('seaborn')
    
    # 1. Media Type Distribution
    logger.info("Creating media type distribution plot")
    plt.figure(figsize=(10, 6))
    df['media_type'].value_counts().plot(kind='bar')
    plt.title('Distribution of Media Types')
    plt.xlabel('Media Type')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / 'media_type_distribution.png')
    plt.close()
    
    # 2. Processing Time Distribution
    logger.info("Creating processing time distribution plot")
    plt.figure(figsize=(10, 6))
    sns.histplot(data=df, x='processing_time', bins=30)
    plt.title('Distribution of Processing Times')
    plt.xlabel('Processing Time (seconds)')
    plt.ylabel('Count')
    plt.tight_layout()
    plt.savefig(output_dir / 'processing_time_distribution.png')
    plt.close()
    
    # 3. Error Rate Over Time
    logger.info("Creating error rate plot")
    plt.figure(figsize=(12, 6))
    df['has_error'] = df['error'].notna()
    df['error_rate'] = df['has_error'].rolling(window=20).mean()
    plt.plot(df.index, df['error_rate'])
    plt.title('Error Rate Over Time (20 Record Rolling Average)')
    plt.xlabel('Record Index')
    plt.ylabel('Error Rate')
    plt.tight_layout()
    plt.savefig(output_dir / 'error_rate.png')
    plt.close()
    
    # 4. File Size Distribution by Media Type
    logger.info("Creating file size distribution plot")
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df, x='media_type', y='file_size_bytes')
    plt.title('File Size Distribution by Media Type')
    plt.xlabel('Media Type')
    plt.ylabel('File Size (bytes)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / 'file_size_distribution.png')
    plt.close()
    
    # Save summary statistics
    logger.info("Generating summary statistics")
    stats = {
        'total_records': len(df),
        'media_type_counts': df['media_type'].value_counts().to_dict(),
        'error_count': df['error'].notna().sum(),
        'avg_processing_time': df['processing_time'].mean(),
        'median_processing_time': df['processing_time'].median(),
        'success_rate': 1 - (df['error'].notna().sum() / len(df))
    }
    
    return stats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-file', required=True, help='Input parquet file')
    parser.add_argument('--output-dir', required=True, help='Output directory for graphs')
    parser.add_argument('--log-file', required=True, help='Log file path')
    args = parser.parse_args()
    
    # Setup
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logging(args.log_file)
    
    try:
        # Load data
        logger.info(f"Loading data from {args.input_file}")
        df = load_parquet_data(args.input_file)
        logger.info(f"Loaded {len(df)} records")
        
        # Create graphs
        stats = create_graphs(df, output_dir, logger)
        
        # Save statistics
        logger.info("Saving statistics")
        with open(output_dir / 'statistics.txt', 'w') as f:
            for key, value in stats.items():
                f.write(f"{key}: {value}\n")
        
    except Exception as e:
        logger.error(f"Error processing data: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main() 