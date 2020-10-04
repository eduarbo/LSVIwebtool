export PROJECT=lsvi-cutout-290921
export KEY_NAME=my-key2
export KEY_DISPLAY_NAME='my-key2'
export flaskapp_id=97c8955576fb
export bokehapp_id=4323d7b54d2e

#create service account with roles of "editor" and "storage Admin"
gcloud iam service-accounts create ${KEY_NAME} --display-name ${KEY_DISPLAY_NAME}
gcloud iam service-accounts list
gcloud iam service-accounts keys create --iam-account ${KEY_NAME}@${PROJECT}.iam.gserviceaccount.com key.json
gcloud projects add-iam-policy-binding ${PROJECT} --member serviceAccount:${KEY_NAME}@${PROJECT}.iam.gserviceaccount.com --role roles/storage.admin
docker login -u _json_key -p "$(cat key.json)" https://gcr.io
echo -e "tagging to google cloud registry container"
docker tag ${flaskapp_id} gcr.io/${PROJECT}/flaskapp:v1
docker tag ${bokehapp_id} gcr.io/${PROJECT}/bokehapp:v1
echo -e "pushing to google cloud registry container"
docker push gcr.io/${PROJECT}/flaskapp:v1
docker push gcr.io/${PROJECT}/bokehapp:v1

