#!/usr/bin/env python3
"""
Service Registrar - Registers services with the service registry
Runs once on container startup to register all services defined in environment
"""

import os
import json
import time
import requests
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment
REGISTRY_URL = os.getenv('REGISTRY_URL', 'http://localhost:8090')
API_KEY = os.getenv('API_KEY', 'default_api_key')
SERVICES = os.getenv('SERVICES', '[]')
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '5'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))

def register_service(service: Dict[str, Any]) -> bool:
    """
    Register a single service with the registry
    
    Args:
        service: Service configuration dictionary
        
    Returns:
        True if successful, False otherwise
    """
    headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    
    url = f"{REGISTRY_URL}/services"
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Registering service {service['name']} (attempt {attempt + 1}/{MAX_RETRIES})")
            
            response = requests.post(
                url,
                json=service,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully registered service {service['name']}")
                return True
            else:
                logger.error(f"Failed to register service {service['name']}: {response.status_code} - {response.text}")
                
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error registering {service['name']}, will retry...")
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout registering {service['name']}, will retry...")
        except Exception as e:
            logger.error(f"Unexpected error registering {service['name']}: {e}")
        
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
    
    return False

def wait_for_registry() -> bool:
    """
    Wait for the service registry to be available
    
    Returns:
        True if registry is available, False if timeout
    """
    logger.info(f"Waiting for service registry at {REGISTRY_URL}")
    
    for attempt in range(MAX_RETRIES * 2):  # Double retries for initial connection
        try:
            response = requests.get(f"{REGISTRY_URL}/health", timeout=5)
            if response.status_code == 200:
                logger.info("Service registry is available")
                return True
        except:
            pass
        
        time.sleep(RETRY_DELAY)
    
    logger.error("Service registry is not available after maximum retries")
    return False

def main():
    """Main registration process"""
    logger.info("Service Registrar starting...")
    
    # Parse services from environment
    try:
        services = json.loads(SERVICES)
    except json.JSONDecodeError:
        logger.error(f"Invalid SERVICES JSON: {SERVICES}")
        return 1
    
    if not services:
        logger.warning("No services defined in SERVICES environment variable")
        return 0
    
    logger.info(f"Found {len(services)} services to register")
    
    # Wait for registry to be available
    if not wait_for_registry():
        return 1
    
    # Register each service
    success_count = 0
    failed_services = []
    
    for service in services:
        if not isinstance(service, dict):
            logger.error(f"Invalid service configuration: {service}")
            continue
            
        if 'name' not in service or 'host' not in service or 'port' not in service:
            logger.error(f"Service missing required fields (name, host, port): {service}")
            continue
        
        if register_service(service):
            success_count += 1
        else:
            failed_services.append(service['name'])
    
    # Summary
    logger.info(f"Registration complete: {success_count}/{len(services)} services registered successfully")
    
    if failed_services:
        logger.error(f"Failed to register services: {', '.join(failed_services)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
