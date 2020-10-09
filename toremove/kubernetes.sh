#
export PROJECT=lsvi-cutout-290921
export CLUSTER=my-first-cluster-1
export REGION=us-central1-c
export VERSION=1.18.6-gke.4801
#create cluster
#gcloud container clusters create ${CLUSTER} --num-nodes 3
#    --cluster-version ${VERSION}
#    --machine-type g1-small
#    --region ${REGION}

#conect to cluster
gcloud container clusters get-credentials ${CLUSTER} --region ${REGION} --project ${PROJECT}

kubectl create -f rc-file.yaml
kubectl create -f service-file.yaml

#to stop kubernetes services
kubectl delete -f rc-file.yaml
kubectl delete -f service-file.yaml

#to see services
kubectl get services

#to see pods in cluster
kubectl get pods
#to see logs of pods
kubectl logs <pod-name> <container-name>
