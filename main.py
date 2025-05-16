import re
import os
import time
import json
from playwright.sync_api import Playwright, sync_playwright, expect

def run(playwright: Playwright) -> None:
    # Read critical values from environment variables
    github_credentials = os.environ.get('GT_PW', '').strip().split()
    if len(github_credentials) >= 2:
        github_username = github_credentials[0]
        github_password = github_credentials[1]
    else:
        print("Warning: GT_PW environment variable not properly set, using defaults")
        github_username = ""
        github_password = ""
    
    docker_image = os.environ.get('DOCKER', '')
    server_name = os.environ.get('SERVER_NAME', 'ss')
    env_vars_content = os.environ.get('ENVSET', """
""")
    # Replace literal \n with actual newlines if they exist
    if '\\n' in env_vars_content:
       env_vars_content = env_vars_content.replace('\\n', '\n')
    browser = playwright.firefox.launch(headless=True)
    context = browser.new_context()
    
    # Check if cookies file exists and load it
    cookies_file = "sliplane_cookies.json"
    if os.path.exists(cookies_file):
        try:
            with open(cookies_file, "r") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            print("Cookies loaded successfully")
        except Exception as e:
            print(f"Error loading cookies: {e}")
    
    page = context.new_page()
    
    try:
        # Go to login page first
        print("Accessing login page to check cookie validity...")
        page.goto("https://sliplane.io/auth/login")
        page.wait_for_timeout(15000)
        
        # If automatically redirected to app page, cookies are valid
        if "/app" in page.url:
            print("Cookie login successful - already redirected to app page!")
        else:
            # Need to perform login with credentials
            print("Cookies invalid or not present, proceeding with password login...")
            perform_login(page, github_username, github_password)
            
            # Check if login was successful by verifying redirect to app page
            if "/app" in page.url:
                print("Password login successful!")
                # Save cookies after successful login
                cookies = context.cookies()
                with open(cookies_file, "w") as f:
                    json.dump(cookies, f)
                print("Cookies saved successfully")
            else:
                print("Login failed - not redirected to app page")
                raise Exception("Login process failed")
    except Exception as e:
        print(f"Error during login process: {e}")
    
    # Continue with the rest of operations, wrapping each section in try/except
    try:
        delete_existing_server(page, server_name)
    except Exception as e:
        print(f"Error during server deletion: {e}. Continuing with next steps...")
    
    try:
        create_new_server(page, server_name)
    except Exception as e:
        print(f"Error during server creation: {e}. Continuing with next steps...")
    
    try:
        deploy_docker_service(page, docker_image, env_vars_content)
    except Exception as e:
        print(f"Error during docker deployment: {e}. Continuing with next steps...")
    
    # Close session
    try:
        page.close()
        context.close()
        browser.close()
    except Exception as e:
        print(f"Error during cleanup: {e}")

def perform_login(page, github_username, github_password):
    """Handle the login process"""
    # We're already on the login page at this point
    page.wait_for_timeout(3000)
    
    # Click login with GitHub
    page.get_by_role("button", name="Login With Github").click()
    page.wait_for_timeout(5000)
    
    # Fill in GitHub credentials
    page.get_by_label("Username or email address").fill(github_username)
    page.get_by_label("Password").fill(github_password)
    page.get_by_role("button", name="Sign in", exact=True).click()
    
    # Wait for redirect after login
    page.wait_for_timeout(10000)

def delete_existing_server(page, server_name):
    """Try to delete existing server if it exists"""
    print(f"Attempting to delete existing server named '{server_name}'...")
    page.goto("https://sliplane.io/app")
    page.wait_for_timeout(3000)
    
    page.locator("[data-test-id=\"sidebar-servers-link\"]").click()
    page.wait_for_timeout(2000)
    
    # Check if there are servers in the list
    server_exists = page.locator("[data-test-id=\"servers-list\"]").count() > 0
    
    if server_exists:
        page.locator("[data-test-id=\"servers-list\"] [data-test-id=\"menu-expand-button\"]").click()
        page.wait_for_timeout(1000)
        page.locator("[data-test-id=\"menu-item-Settings\"]").click()
        page.wait_for_timeout(1000)
        page.get_by_role("link", name="Unsafe Territory").click()
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Delete Server").click()
        page.wait_for_timeout(1000)
        page.get_by_placeholder("Enter command here").fill(f"sudo rm -f {server_name}")
        page.locator("form").get_by_role("button", name="Delete Server").click()
        page.wait_for_timeout(5000)
        print("Server deleted successfully")
    else:
        print("No existing server found to delete")

def create_new_server(page, server_name):
    """Create a new server"""
    print(f"Creating new server named '{server_name}'...")
    page.locator("[data-test-id=\"sidebar-projects-link\"]").click()
    page.wait_for_timeout(2000)
    
    page.get_by_role("link", name="Default project").click()
    page.wait_for_timeout(2000)
    
    # Find and click the deploy service button
    try:
        page.locator("[data-test-id=\"empty-list\"]").get_by_role("button", name="Deploy Service").click()
    except Exception:
        # Alternative selector if the previous one fails
        page.get_by_role("button", name="Deploy Service").click()
    
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="Create Server").click()
    page.wait_for_timeout(1000)
    
    # Select location
    page.locator("#location-dropdown-invoke").click()
    page.wait_for_timeout(1000)
    page.get_by_role("button", name="Singapore Select").click()
    page.wait_for_timeout(1000)
    
    # Set server name
    page.get_by_placeholder("My awesome Server").fill(server_name)
    page.wait_for_timeout(1000)
    
    # Create the server
    page.get_by_role("button", name="Create Demo Server").click()
    page.wait_for_timeout(8000)
    print("Server created successfully")

def deploy_docker_service(page, docker_image, env_vars_content):
    """Deploy Docker service to the server"""
    print(f"Deploying Docker image '{docker_image}'...")
    # Click on the server (using dynamic server name)
    server_name = os.environ.get('SERVER_NAME', 'ss')
    page.get_by_role("button", name=server_name).click()
    page.wait_for_timeout(2000)
    
    # Deploy Docker image
    page.get_by_role("button", name="Registry Deploy a Docker").click()
    page.wait_for_timeout(2000)
    
    # Set Docker image
    page.get_by_placeholder("docker.io/username/image:tag").fill(docker_image)
    page.wait_for_timeout(1000)
    
    # Configure environment variables
    page.get_by_role("button", name="From .env file").click()
    page.wait_for_timeout(1000)
    
    # Use provided environment variables
    page.get_by_placeholder("KEY_1=VALUE_1\nKEY_2=VALUE_2\nKEY_3=VALUE_3").fill(env_vars_content)
    page.wait_for_timeout(1000)
    
    page.get_by_role("button", name="Apply").click()
    page.wait_for_timeout(1000)
    
    # Deploy the service
    page.locator("[data-test-id=\"deploy-button\"]").click()
    page.wait_for_timeout(5000)
    print("Docker service deployed successfully")
    page.wait_for_timeout(8000)

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
