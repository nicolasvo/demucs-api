FROM demucs:base
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.3 /lambda-adapter /opt/extensions/lambda-adapter

ENV AWS_LWA_INVOKE_MODE=response_stream
ENV AWS_LWA_PORT=8000
ENV TORCH_HOME=/tmp

WORKDIR /app
COPY lambda.py .env /app/

ENTRYPOINT [ "python" ]
CMD [ "lambda.py" ]
