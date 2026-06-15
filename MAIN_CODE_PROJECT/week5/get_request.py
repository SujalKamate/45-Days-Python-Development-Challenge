# ==========================================================
# Advanced API GET Request Example using Python requests
# API: JSONPlaceholder
# ==========================================================
#
# Features included:
# 1. Uses requests library
# 2. Sends GET request to API
# 3. Uses headers
# 4. Error handling (try-except)
# 5. Request timeout
# 6. Prints status code
# 7. Prints response headers
# 8. Converts JSON response to dictionary
# 9. Displays data in formatted style
# 10. Checks request success
# 11. Shows execution time
# 12. Detailed comments explaining every line
#
# ==========================================================


# Import requests library
# Used to make HTTP requests
import requests

# Import time module
# Used for measuring request execution time
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

# Store the API endpoint inside a variable (loaded from env, with fallback to default)
url = os.getenv("GET_REQUEST_URL", "https://jsonplaceholder.typicode.com/posts/1")


# ==========================================================
# Request Headers
# ==========================================================

# Headers contain additional information sent
# to the server with the request

headers = {
    
    # User-Agent identifies the client application
    "User-Agent": "Python API Learning Project",

    # Accept tells server expected response type
    "Accept": "application/json"
}


# ==========================================================
# Start timer
# ==========================================================

# Record current time before request starts
start_time = time.time()


# ==========================================================
# Error handling block
# ==========================================================

try:

    # ======================================================
    # Send GET Request
    # ======================================================

    # timeout=5 means wait maximum 5 seconds (loaded from environment, with fallback to default)
    # If API takes longer than this,
    # request automatically fails
    try:
        timeout = float(os.getenv("GET_REQUEST_TIMEOUT", "5"))
    except ValueError:
        timeout = 5.0

    response = requests.get(
        url,
        headers=headers,
        timeout=timeout,
        verify=True
    )


    # ======================================================
    # Calculate execution time
    # ======================================================

    end_time = time.time()

    total_time = end_time - start_time


    # ======================================================
    # Print status information
    # ======================================================

    print("\n========== REQUEST DETAILS ==========")

    print("Status Code:", response.status_code)

    print("Request URL:", response.url)

    print("Request Method: GET")

    print("Response Time:",
          round(total_time,4),
          "seconds")


    # ======================================================
    # Check if request succeeded
    # ======================================================

    # Status codes between 200 and 299
    # indicate success

    if response.status_code == 200:

        print("\nRequest Successful")


        # ==============================================
        # Convert JSON response to dictionary
        # ==============================================

        data = response.json()


        # ==============================================
        # Print response headers
        # ==============================================

        print("\n========== RESPONSE HEADERS ==========")

        for key, value in response.headers.items():

            print(f"{key}: {value}")


        # ==============================================
        # Print complete raw response
        # ==============================================

        print("\n========== RAW RESPONSE ==========")

        print(data)


        # ==============================================
        # Display formatted data
        # ==============================================

        print("\n========== FORMATTED DATA ==========")

        print("User ID :", data["userId"])

        print("Post ID :", data["id"])

        print("Title   :", data["title"])

        print("Body    :", data["body"])


        # ==============================================
        # Additional statistics
        # ==============================================

        print("\n========== EXTRA INFO ==========")

        print(
            "Title Length:",
            len(data["title"]),
            "characters"
        )

        print(
            "Body Length:",
            len(data["body"]),
            "characters"
        )

        print(
            "Total Fields:",
            len(data)
        )

    else:

        print(
            "\nRequest failed with code:",
            response.status_code
        )


# ==========================================================
# Exception handling
# ==========================================================

# Runs if connection timeout occurs
except requests.exceptions.Timeout:

    print(
        "Error: Request timed out"
    )


# Runs if connection problem occurs
except requests.exceptions.ConnectionError:

    print(
        "Error: Internet connection issue"
    )


# Runs for invalid URLs
except requests.exceptions.InvalidURL:

    print(
        "Error: Invalid URL"
    )


# Runs for all request-related errors
except requests.exceptions.RequestException as e:

    print(
        "General Request Error:"
    )

    print(e)


# Runs for any unexpected error
except Exception as e:

    print(
        "Unexpected Error:"
    )

    print(e)


# ==========================================================
# Program End Message
# ==========================================================

print("\nProgram Execution Finished")
