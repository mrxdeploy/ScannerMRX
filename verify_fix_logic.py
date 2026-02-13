
import unittest
from unittest.mock import MagicMock
import numpy as np
import sys
import os

# Add the project directory to sys.path
sys.path.append("c:\\Users\\User\\ScannerMRX")

# Mock dependencies before importing embedding_engine
sys.modules['database'] = MagicMock()
sys.modules['open_clip'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['PIL'] = MagicMock()

# Now import the class to test
# We need to bypass the actual init which loads models and DB
from embedding_engine import EmbeddingEngine

class TestClassificationLogic(unittest.TestCase):
    def test_single_best_match_priority(self):
        """
        Verify that a class with a single high-scoring match wins over 
        a class with a better average but lower max score.
        """
        engine = EmbeddingEngine.__new__(EmbeddingEngine)
        engine.embeddings_cache = {}
        engine.image_paths_cache = {}
        
        # Scenario:
        # Class A: "Consistent Moderate"
        # - Image 1: 0.81 similarity
        # - Image 2: 0.81 similarity
        # -> Average: 0.81, Max: 0.81
        
        # Class B: "One Hit Wonder"
        # - Image 1: 0.87 similarity (The Winner!)
        # - Image 2: 0.10 similarity
        # -> Average: ~0.48, Max: 0.87
        
        # OLD Logic would pick Class A (0.81 avg > 0.48 avg)
        # NEW Logic should pick Class B (0.87 max > 0.81 max)
        
        # Mocking the data structures
        # We need to mock generate_embedding_from_bytes and the dot product logic,
        # OR we can just inject values into the loop if we refactor.
        # Since we can't easily refactor the loop in the test without changing code,
        # we will mock the vectors to produce the desired dot product results.
        
        # simplified: query vector = [1.0, 0.0]
        # Class A vectors: [0.81, 0.58...], [0.81, 0.58...] -> dot product ~ 0.81
        # Class B vectors: [0.87, 0.49...], [0.10, 0.99...] -> dot product ~ 0.87 and 0.10
        
        engine.embeddings_cache = {
            "Class A": np.array([[0.81, 0.0], [0.81, 0.0]]),
            "Class B": np.array([[0.87, 0.0], [0.10, 0.0]])
        }
        
        engine.image_paths_cache = {
            "Class A": [{"path": "a1.jpg", "classification": "Class A"}, {"path": "a2.jpg", "classification": "Class A"}],
            "Class B": [{"path": "b1.jpg", "classification": "Class B"}, {"path": "b2.jpg", "classification": "Class B"}]
        }
        
        # Mock generate_embedding_from_bytes to return our "query" vector
        engine.generate_embedding_from_bytes = MagicMock(return_value=np.array([1.0, 0.0]))
        
        # Run classification
        result = engine.classify_image(b"fake_image_bytes")
        
        print(f"Result Classification: {result['classification']}")
        print(f"Result Score: {result['similarity_score']}")
        print(f"Top 3 Matches: {[(m['classification'], m['similarity']) for m in result['top_matches']]}")
        
        # Assertions
        self.assertEqual(result['classification'], "Class B", "Should pick Class B due to highest single match")
        self.assertEqual(result['similarity_score'], 87.0, "Score should be 87.0")
        self.assertEqual(result['status'], "match")

if __name__ == '__main__':
    unittest.main()
