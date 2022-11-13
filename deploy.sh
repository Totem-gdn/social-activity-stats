#!/bin/bash

echo -e "\n Building Docker image...."
sudo docker build -t 667950714614.dkr.ecr.us-east-1.amazonaws.com/discord-activity-to-mixpanel:latest --no-cache .
echo -e "===== Docker image has been built....\n\n"

echo -e "Pushing image to repository..."
aws ecr get-login-password --region us-east-1 --profile totem | sudo docker login --username AWS --password-stdin 667950714614.dkr.ecr.us-east-1.amazonaws.com
sudo docker push 667950714614.dkr.ecr.us-east-1.amazonaws.com/discord-activity-to-mixpanel:latest
#aws eks update-kubeconfig --name totem --region us-east-1 --profile totem
#kubectl delete pods `kubectl get pods | grep discord-activity-to-mixpanel | awk '{print $1}'`

echo -e "\n===== Rolling out updated deployment...."
kubectl rollout status deployment/discord-activity-to-mixpanel
