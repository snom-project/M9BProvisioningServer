sudo docker rm -f $(sudo docker ps -a -q --filter="ancestor=m9bprov");
sudo bash build.sh;sudo docker kill $(sudo docker ps -a -q --filter="ancestor=m9bprov");  sudo bash run.sh

#sudo sh build.sh;sudo docker kill $(sudo docker ps -q  --format="{{.ID}}");  sudo sh run.sh 
