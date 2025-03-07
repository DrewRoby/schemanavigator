# SchemaNavigator

A Django application for tracking and visualizing schema evolution over time.

## Features

- Ingest datasets and automatically detect schemas and primary keys
- Track schema changes over time
- Associate source files with schema concepts
- Visualize metadata about primary keys and compare schemas

## Setup

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install requirements:
   ```
   pip install -r requirements.txt
   ```

3. Configure environment variables in a `.env` file.

4. Run migrations:
   ```
   python manage.py migrate
   ```

5. Start the development server:
   ```
   python manage.py runserver
   ```
