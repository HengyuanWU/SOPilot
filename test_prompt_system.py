#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the new YAML-based prompt system.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'src'))

import logging
from app.services.prompt_service import prompt_service
from app.services.llm_service import llm_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_prompt_service():
    """Test basic PromptService functionality."""
    print("🧪 Testing PromptService...")
    
    try:
        # Test listing prompts
        prompts = prompt_service.list_prompts()
        print(f"✅ Found {len(prompts)} prompt files")
        
        for prompt in prompts[:3]:  # Show first 3
            print(f"  - {prompt['id']} ({prompt['agent']}, {prompt['locale']})")
        
        # Test binding resolution
        binding = prompt_service.resolve_binding(
            target_type="agent",
            target_id="planner",
            locale="zh"
        )
        print(f"✅ Planner binding: {binding.provider}:{binding.model}")
        
        # Test template validation
        variables = {
            "topic": "测试主题",
            "chapter_count": 3,
            "language": "中文"
        }
        
        result = llm_service.validate_template(
            agent_name="planner",
            variables=variables,
            locale="zh"
        )
        
        if result["valid"]:
            print("✅ Template validation successful")
            print(f"  Messages count: {len(result['messages'])}")
        else:
            print(f"❌ Template validation failed: {result['errors']}")
            
    except Exception as e:
        print(f"❌ PromptService test failed: {e}")
        return False
    
    return True


def test_agent_info():
    """Test agent information retrieval."""
    print("\n🔍 Testing Agent Info...")
    
    agents = ["planner", "researcher", "writer", "validator", "qa_generator", "kg_builder"]
    
    for agent in agents:
        try:
            info = llm_service.get_agent_info(agent, "zh")
            if info["available"]:
                print(f"✅ {agent}: {info['provider']}:{info['model']}")
            else:
                print(f"❌ {agent}: {info.get('error', 'Not available')}")
        except Exception as e:
            print(f"❌ {agent}: {e}")


def test_yaml_loading():
    """Test YAML file loading and parsing."""
    print("\n📄 Testing YAML Loading...")
    
    test_files = [
        "agents/planner.zh.yaml",
        "agents/researcher.subchapter.zh.yaml", 
        "agents/writer.zh.yaml",
        "prompt_bindings.yaml"
    ]
    
    for file_path in test_files:
        try:
            data = prompt_service._load_yaml(file_path)
            print(f"✅ {file_path}: loaded successfully")
            
            if "messages" in data:
                print(f"  Messages: {len(data['messages'])}")
            if "bindings" in data:
                print(f"  Bindings: {len(data['bindings'])}")
                
        except Exception as e:
            print(f"❌ {file_path}: {e}")


def main():
    """Run all tests."""
    print("🚀 Starting Prompt Hub Test Suite")
    print("=" * 50)
    
    # Test PromptService
    if not test_prompt_service():
        print("\n❌ PromptService tests failed!")
        return False
    
    # Test agent info
    test_agent_info()
    
    # Test YAML loading
    test_yaml_loading()
    
    print("\n" + "=" * 50)
    print("✨ All tests completed!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)