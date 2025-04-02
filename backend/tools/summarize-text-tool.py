#!/usr/bin/env python
"""
A tool that summarizes text content to a specified length.
Uses simple extractive summarization techniques.
"""
import sys
import json
import re
from collections import Counter
import math

def preprocess_text(text):
    """Clean and preprocess text for summarization."""
    # Replace newlines with spaces
    text = re.sub(r'\n+', ' ', text)
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def split_into_sentences(text):
    """Split text into sentences."""
    # Basic sentence splitting - can be improved with NLP libraries
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', text)
    return [s.strip() for s in sentences if s.strip()]

def calculate_word_frequencies(text):
    """Calculate word frequencies excluding stopwords."""
    # Simple stopwords list - can be expanded
    stopwords = set([
        'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 
        'about', 'and', 'or', 'but', 'if', 'of', 'as', 'is', 'are', 'was', 
        'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 
        'did', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 
        'it', 'we', 'they'
    ])
    
    # Tokenize and filter
    words = re.findall(r'\b\w+\b', text.lower())
    words = [word for word in words if word not in stopwords]
    
    # Count frequencies
    return Counter(words)

def score_sentences(sentences, word_freq):
    """Score sentences based on word frequencies."""
    scores = []
    for sentence in sentences:
        words = re.findall(r'\b\w+\b', sentence.lower())
        score = sum(word_freq[word] for word in words if word in word_freq)
        # Normalize by sentence length to avoid bias toward longer sentences
        if len(words) > 0:
            score = score / len(words)
        scores.append(score)
    return scores

def summarize_text(text, max_sentences=3, max_chars=None):
    """
    Summarize text by extracting the most important sentences.
    
    Args:
        text (str): Text to summarize
        max_sentences (int): Maximum number of sentences to include
        max_chars (int, optional): Maximum character length of summary
        
    Returns:
        str: Summarized text
    """
    # Preprocess
    text = preprocess_text(text)
    sentences = split_into_sentences(text)
    
    # If text is already short, return as is
    if len(sentences) <= max_sentences:
        return text
    
    # Calculate word frequencies
    word_freq = calculate_word_frequencies(text)
    
    # Score sentences
    scores = score_sentences(sentences, word_freq)
    
    # Create (index, score) pairs and sort by score
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    
    # Select top sentences
    top_indices = [idx for idx, _ in ranked[:max_sentences]]
    
    # Sort by original position to maintain text flow
    top_indices.sort()
    
    # Reconstruct summary
    summary = " ".join(sentences[idx] for idx in top_indices)
    
    # Truncate to max_chars if specified
    if max_chars and len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(' ', 1)[0] + '...'
    
    return summary

def main():
    # Read JSON input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({
            "error": "Invalid JSON input",
            "status": "error"
        }))
        sys.exit(1)
    
    # Extract parameters
    text = input_data.get('text', '')
    max_sentences = input_data.get('max_sentences', 3)
    max_chars = input_data.get('max_chars')
    
    # Validate input
    if not text:
        print(json.dumps({
            "error": "No text provided",
            "status": "error"
        }))
        sys.exit(1)
    
    # Generate summary
    try:
        summary = summarize_text(text, max_sentences, max_chars)
        
        # Return result as JSON
        result = {
            "summary": summary,
            "original_length": len(text),
            "summary_length": len(summary),
            "reduction_percent": round((1 - len(summary) / len(text)) * 100, 1),
            "sentences_count": len(split_into_sentences(summary)),
            "status": "success"
        }
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "status": "error"
        }))
        sys.exit(1)

if __name__ == "__main__":
    main()
