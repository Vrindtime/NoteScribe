# 1. Use the official AWS Lambda Python 3.12 Base Image (AL2023)
# This includes the RIC and is optimized for Lambda.
FROM public.ecr.aws/lambda/python:3.12

# 2. Set the working directory
# LAMBDA_TASK_ROOT is where Lambda expects your application code.
WORKDIR ${LAMBDA_TASK_ROOT}

# For AL2023 (which 3.12 uses), we use 'dnf groupinstall'
RUN dnf -y update && \ 
    dnf -y install gcc gcc-c++ python3-devel && \ 
    dnf clean all

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

EXPOSE 8000

# Set the ENTRYPOINT to the Python module for the RIC
# This tells the container what executable to run first.
ENTRYPOINT [ "python", "-m", "awslambdaric" ]

# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD [ "app.main.handler" ]