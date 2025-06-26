## IPMA Expert Project: Installation Guide

Follow these steps to set up the **IPMA Expert** project. This guide assumes you have Python and Git installed.

### **Prerequisites**

- Python 3.8+ installed
- Git installed
- [ollama](https://ollama.com/) installed


### **1. Install Ollama**

Make sure you have Ollama installed on your system.

```sh
# For macOS
brew install ollama

# For Linux
curl -fsSL https://ollama.com/install.sh | sh

# For Windows
# Download and install from https://ollama.com/download
```


### **2. Pull the mistral:latest Model**

Before proceeding, pull the `mistral:latest` model using Ollama:

```sh
ollama pull mistral:latest
```


### **3. Clone the IPMA Expert Repository**

Clone the project repository from GitHub (replace `https://github.com/migcruzz/Ipma-Expert.git` with the actual URL):

```sh
git clone https://github.com/migcruzz/Ipma-Expert.git ipma-expert
cd ipma-expert
```


### **4. Create and Activate a Virtual Environment**

Set up a Python virtual environment to isolate project dependencies:

```sh
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```


### **5. Install Project Dependencies**

Install all required Python packages:

```sh
pip install -r requirements.txt
```


### **6. Run the Project**

Start the project (replace with the actual run command if different):

```sh
python main.py
```


### **Summary Table**

| Step | Description | Command/Action |
| :-- | :-- | :-- |
| 1 | Install Ollama | `brew install ollama` / `curl ...` / Download |
| 2 | Pull mistral:latest model | `ollama pull mistral:latest` |
| 3 | Clone repository | `git clone https://github.com/migcruzz/Ipma-Expert.git ipma-expert` |
| 4 | Create \& activate virtual environment (venv) | `python3 -m venv venv` + `source venv/bin/activate` |
| 5 | Install dependencies | `pip install -r requirements.txt` |
| 6 | Run the project | `python main.py` |

Your **IPMA Expert** environment is now ready!

