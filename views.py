@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def seo_head_checker(request):
    """
    Renders the SEO Head Checker form and handles POST requests to initiate processing.

    - For GET requests: Displays the form for the user to input a sitemap URL.
    - For POST requests: Validates the submitted form and initiates sitemap processing.
    - Provides user feedback on errors or the status of the initiated process.
    """
    # Handle form submission via POST.
    if request.method == "POST":
        # Bind the submitted data to the form for validation.
        form = SitemapForm(request.POST)
        # Check if the form data is valid
        if form.is_valid():
            # Extract the cleaned sitemap URL from the form.
            sitemap_url = form.cleaned_data["sitemap_url"]
            try:
                # Start processing the sitemap and get the response.
                response = start_sitemap_processing(request)
                # Task successfully started.
                if response.status_code == 202:
                    # Retrieve the task ID for tracking the status.
                    task_id = response.json().get("task_id")
                    # Pass form and task_id to template.
                    return render(
                        request,
                        "projects/seo_head_checker.html",
                        {"form": form, "task_id": task_id},
                    )
                # If the response indicates an error.
                else:
                    # Extract the error message or provide a generic error.
                    error_message = response.json().get("error", "Unexpected error.")
                    # Pass error to template.
                    return render(
                        request,
                        "projects/seo_head_checker.html",
                        {"form": form, "error": error_message},
                    )
            # Catch any unexpected errors during processing.
            except Exception as e:
                # Render the form with an error message.
                return render(
                    request,
                    "projects/seo_head_checker.html",
                    {"form": form, "error": str(e)},
                )
    # Handle GET requests by displaying an empty form.
    else:
        form = SitemapForm()

    # Render the form for both GET and unsuccessful POST requests.
    return render(request, "projects/seo_head_checker.html", {"form": form})


def start_sitemap_processing(request):
    """
    Handles the initiation of sitemap processing.

    - Accepts a POST request with a sitemap URL in the request body.
    - Starts a background task to fetch and process the sitemap URLs.
    - Returns a JSON response containing a unique task ID for progress tracking.
    """
    # Ensure the request method is POST.
    if request.method == "POST":
        try:
            # Parse the request body as JSON.
            data = json.loads(request.body)
            # Normalize and validate the sitemap URL.
            sitemap_url = normalize_url(data.get("sitemap_url"))

            # Generate a unique task ID for this processing job.
            task_id = str(uuid.uuid4())
            # Initialize the cache for tracking task status and progress.
            cache.set(task_id, {"status": "pending", "progress": 0}, timeout=1800)

            # Define the background task for sitemap processing.
            def process_task():
                try:
                    # Fetch all URLs from the sitemap.
                    urls = fetch_sitemap_urls(sitemap_url)
                    # Process the fetched URLs, updating progress in cache.
                    results = process_sitemap_urls(urls, max_workers=5, task_id=task_id)
                    # Save the processed results to a CSV file.
                    file_path = save_results_to_csv(results, task_id)
                    # Update cache to mark task as completed and store the file path.
                    cache.set(
                        task_id,
                        {"status": "completed", "file": file_path},
                        timeout=1800,
                    )
                except Exception as e:
                    # Update cache to indicate an error occurred.
                    cache.set(
                        task_id, {"status": "error", "error": str(e)}, timeout=1800
                    )
                finally:
                    # Explicit cleanup.
                    del urls, results
                    # Perform garbage collection to free up memory.
                    gc.collect()

            # Submit the processing task to a thread pool for background execution.
            ThreadPoolExecutor().submit(process_task)

            # Return a response with the task ID for the client to track progress.
            return JsonResponse({"task_id": task_id}, status=202)
        except Exception as e:
            # Handle any exceptions during processing and return an error response.
            return JsonResponse({"error": str(e)}, status=400)

    # Return an error response if the request method is not POST.
    return JsonResponse({"error": "Invalid request method"}, status=405)


def get_task_status(request, task_id):
    """
    Retrieves the status of a background task by its task ID.

    - Checks the cache for the task information associated with the given task ID.
    - Returns the current status of the task, including progress or errors, if available.

    Args:
        request (HttpRequest): The HTTP request object.
        task_id (str): The unique identifier for the task.

    Returns:
        JsonResponse: A JSON response containing the task status or an error message.
    """
    # Attempt to retrieve the task information from the cache.
    task = cache.get(task_id)
    # If the task is not found in the cache.
    if not task:
        # Return an error response indicating the task was not found.
        return JsonResponse({"error": "Task not found"}, status=404)
    # Return the task details as a JSON response.
    return JsonResponse(task)


def download_task_file(request, task_id):
    """
    Handles the download of a completed task's output file.

    - Checks the cache for the task information and ensures the task is completed.
    - Validates the existence of the output file associated with the task.
    - Serves the file for download and cleans up the file and cache entry after serving.

    Args:
        request (HttpRequest): The HTTP request object.
        task_id (str): The unique identifier for the task.

    Returns:
        HttpResponse: A response containing the file for download.
        JsonResponse: An error response if the file or task is not found.
    """
    # Retrieve task details from the cache.
    task = cache.get(task_id)
    # Ensure the task exists and is marked as "completed".
    if not task or task.get("status") != "completed":
        return JsonResponse({"error": "File not ready or task not found"}, status=404)

    # Get the file path from the task details.
    file_path = task.get("file")

    # Verify that the file path exists and is accessible.
    if not file_path or not os.path.exists(file_path):
        return JsonResponse({"error": "File not found"}, status=404)

    # Open the file in binary mode and prepare the response for download.
    with open(file_path, "rb") as file:
        response = HttpResponse(file, content_type="application/octet-stream")

        # Set the Content-Disposition header to prompt a download with the file's name.
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(file_path)}"'
        )

        # Remove the file from the server after it is served.
        os.remove(file_path)
        # Delete the task entry from the cache.
        cache.delete(task_id)
        # Trigger garbage collection to free memory.
        gc.collect()

        # Return the file as an HTTP response.
        return response
