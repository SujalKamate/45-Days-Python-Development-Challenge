# ==========================================================
# Fetch User Information from API
# ==========================================================
#
# Features:
# 1. Uses requests library
# 2. Sends GET request
# 3. Uses error handling
# 4. Uses timeout protection
# 5. Converts JSON response to dictionary
# 6. Extracts selected fields only
# 7. Displays formatted output
# 8. Adds extra validation
# 9. Fully commented for beginners
#
# ==========================================================


# Import requests module
# Used for making API requests
import requests

# Import time module
# Used to measure response time
import time

# Import os for environment variables
import os

# Import load_dotenv from python-dotenv
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ==========================================================
# API URL
# ==========================================================

# Store API URL in a variable (loaded from env, with fallback to default)
url = os.getenv("FETCH_DETAILS_URL", "https://jsonplaceholder.typicode.com/users/1")


# ==========================================================
# Request Headers
# ==========================================================

headers = {

    # Identifies the client application
    "User-Agent": "Python Learning API Project",

    # Expected response type
    "Accept": "application/json"
}


# ==========================================================
# Start Timer
# ==========================================================

start = time.time()


# ==========================================================
# Error Handling Block
# ==========================================================

try:

    # Get timeout from environment with a fallback default
    try:
        timeout = float(os.getenv("FETCH_DETAILS_TIMEOUT", "5"))
    except ValueError:
        timeout = 5.0

    # Send GET request to server
    response = requests.get(
        url,
        headers=headers,
        timeout=timeout,
        verify=True
    )


    # Calculate request time
    end = time.time()

    total_time = end - start


    # ======================================================
    # Print Request Information
    # ======================================================

    print("\n========== REQUEST INFO ==========")

    print("URL:", response.url)

    print("Status Code:", response.status_code)

    print(
        "Response Time:",
        round(total_time,4),
        "seconds"
    )


    # ======================================================
    # Check successful response
    # ======================================================

    if response.status_code == 200:

        print("\nData fetched successfully")


        # Convert response JSON
        # into Python dictionary
        user = response.json()


        # ==================================================
        # Extract only required fields
        # ==================================================

        name = user.get("name", "Not Available")

        email = user.get("email", "Not Available")

        phone = user.get("phone", "Not Available")

        website = user.get("website", "Not Available")


        # ==================================================
        # Print Required Fields
        # ==================================================

        print("\n========== USER DETAILS ==========")

        print("Name    :", name)

        print("Email   :", email)

        print("Phone   :", phone)

        print("Website :", website)


        # ==================================================
        # Extra Information
        # ==================================================

        print("\n========== EXTRA DETAILS ==========")

        print(
            "Name Length:",
            len(name)
        )

        print(
            "Email Length:",
            len(email)
        )

        print(
            "Phone Length:",
            len(phone)
        )


    else:

        print(
            "Failed to fetch data"
        )


# ==========================================================
# Exception Handling
# ==========================================================

except requests.exceptions.Timeout:

    print(
        "Error: Request Timeout"
    )


except requests.exceptions.ConnectionError:

    print(
        "Error: Connection Problem"
    )


except requests.exceptions.InvalidURL:

    print(
        "Error: Invalid URL"
    )


except requests.exceptions.RequestException as e:

    print(
        "Request Error:",
        e
    )


except Exception as e:

    print(
        "Unexpected Error:",
        e
    )


# ==========================================================
# Program End
# ==========================================================

print("\nProgram Finished")
