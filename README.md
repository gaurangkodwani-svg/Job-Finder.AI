# AI Job Finder (Python Version)

A lightweight Python implementation of the AI Job Finder, built using FastAPI and SQLite.

## 🚀 Features

- **Hybrid TF-IDF Matching**: Custom matching engine powered by text similarity scoring.
- **SQLite Storage**: Light, self-contained relational database management.
- **Resume Parsing**: Straightforward processing of raw resume text into profile data.
- **Score-Based Job Recommendations**: Instant, ranked job recommendations based on skills and background.
- **Streamlined Codebase**: All previous premium code paths completely removed.

## 🛠️ Tech Stack

- **Framework**: FastAPI
- **Database**: SQLite
- **Core Libraries**: `scikit-learn` (for TF-IDF vectorization), `pydantic` (for data validation)

## 📦 Installation & Setup

### Prerequisites

Ensure you have **Python 3.8+** and **pip** installed on your machine.

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com
   cd ai-job-finder
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the server**
   ```bash
   python app.py
   ```
   The API will be available locally at: `http://localhost:8000`

## 🕹️ API Endpoints

### Users

#### Create a User
* **URL**: `POST /api/users`
* **Payload**:
  ```json
  {
    "email": "user@example.com",
    "name": "John Doe"
  }
  ```

#### Get a User
* **URL**: `GET /api/users/{id}`

---

### Profiles & Parsing

#### Create a Profile
* **URL**: `POST /api/users/{id}/profile`
* **Payload**:
  ```json
  {
    "raw_text": "Resume text here..."
  }
  ```

#### Get a Profile
* **URL**: `GET /api/users/{id}/profile`

---

### Matching Engine

#### Run Match Engine
* **URL**: `POST /api/users/{id}/match`
* **Description**: Triggers the hybrid TF-IDF algorithm to match the user's profile text against available jobs.

#### Get Matches
* **URL**: `GET /api/users/{id}/matches`
* **Description**: Returns a ranked list of job matching profiles with similarity scores.

## 🤝 Contributing

1. Fork the project.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

## 📝 License

Distributed under the MIT License. See `LICENSE` for more details.
