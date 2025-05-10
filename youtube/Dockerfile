FROM node:20

# Install Python and venv
RUN apt-get update && apt-get install -y python3 python3-venv

# Set up Python virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install ytmusicapi inside the venv
RUN pip install --no-cache-dir ytmusicapi

# Set working directory
WORKDIR /app

# Copy package files and install Node dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the app
COPY . .

# Expose port
EXPOSE 3000

# Start the server
CMD ["npm", "start"]

