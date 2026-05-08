#!/usr/bin/env python
"""Quick test for search_drugs function."""
import asyncio
import sys
import os

# Add src to path - we're in healthmate root, need ai/services/rag-system/src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ai', 'services', 'rag-system', 'src'))

from rag.medical.drugs_client import search_drugs
from rag.core.config import settings

async def main():
    print(f"Backend URL: {settings.backend_url}")
    print("Testing search_drugs with query: 'головная боль'")
    result = await search_drugs('головная боль', limit=5)
    print(f'Result count: {len(result)}')
    if result:
        for r in result:
            print(f"  - ID: {r.get('id')}, Name: {r.get('tradeName')}")
    else:
        print("  (empty result - search_drugs returned [])")

if __name__ == '__main__':
    asyncio.run(main())
