# ============================================================
# Lecture 5: Docker Demo - Dockerfile
# DevOps for Cyber-Physical Systems | University of Bern
# ============================================================
# This Dockerfile demonstrates the basics of containerizing
# a Python web application.
# ============================================================

# STEP 1: Start with official Python image
# ----------------------------------------------------------
# We use the slim variant for smaller size (~150MB vs ~900MB)
FROM python:3.11-alpine
RUN apk add --no-cache gcc musl-dev linux-headers

                            # FROM python:3.11-slim
                            # RUN apt-get update && apt-get install -y gcc

                            # FROM python:3.11-alpine
                            # RUN apk add --no-cache gcc musl-dev linux-headers
                            # docker build -t myapp:alpine -f Dockerfile .


                            #BUILD TO PUBLISH
                            # docker build -t task-app:v1.0 .
                            # docker login
                            # docker tag task-app:v1.0 climbtheswissapps/task-app:v1.0
                            # docker push climbtheswissapps/task-app:v1.0


                            #DIAGNOSTICS
                            # docker compose logs web
                                # Show output & errors of "web" container
                                # use -f to follow logs in real-time
                            # docker inspect lecture5-web
                                #Returns full JSON details about the container (config, network, mounts, etc.)
                            # docker stats
                                #Live resource usage (CPU, memory) of running containers (Task Manager)

# STEP 2: Set the working directory
# ----------------------------------------------------------
# All subsequent commands run from /app
WORKDIR /app

# STEP 3: Copy and install dependencies FIRST
# ----------------------------------------------------------
# Why separate? Docker layer caching!
# If requirements.txt hasn't changed, this layer is cached
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# STEP 4: Copy application code
# ----------------------------------------------------------
# This layer rebuilds when code changes, but dependencies stay cached
COPY app.py .
COPY templates/ templates/
COPY assets/ assets/

# STEP 5: Expose the port
# ----------------------------------------------------------
# Documents which port the app uses (doesn't publish it)
EXPOSE 5000

# STEP 6: Run the application
# ----------------------------------------------------------
# CMD defines what runs when the container starts
CMD ["python", "app.py"]

# ============================================================
# BUILD:  docker build -t lecture5-webapp .
# RUN:    docker run -p 5000:5000 lecture5-webapp
# ============================================================