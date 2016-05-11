'use strict';

// USAGE
// node tasks/create_image.js \
// <region> \
// <instance_id> \
// <image name> \
// <DayOfWeek> \
// <NoReboot (optional, default true)> \
// <DryRun (optional, default false)>

if (process.argv.length < 5) {
  console.error('not enough arguments provided');
  process.exit(1);
}

const AWS = require('aws-sdk');

const date = new Date();
const region = process.argv[2];
const InstanceId = process.argv[3];
const Name = `${process.argv[4]}-${date.getUTCDate()}-${date.getUTCMonth()}-${date.getUTCFullYear()}`;
const DayOfWeek = process.argv[5];
const NoReboot = process.argv[6] === 'true'
const DryRun = process.argv[7] === 'true';
const accessKeyId = process.env.ACCESS_KEY_ID;
const secretAccessKey = process.env.SECRET_ACCESS_KEY;
const EC2 = new AWS.EC2({ region, accessKeyId, secretAccessKey });
const Description = `Automatically generated AMI for ${InstanceId}`; 
const BlockDeviceMappings = [
  {
    Ebs: {
      DeleteOnTermination: false,
      Encrypted: false,
      DeleteOnTermination: false,
      VolumeType: 'gp2' // General Purpose SSD
    }
  }
];

if (DayOfWeek) {
  if (+DayOfWeek !== date.getDay()) {
    console.log('Not specified Day of Week');
    process.exit(0);
  }
}

EC2.createImage({
  InstanceId,
  Name,
  BlockDeviceMappings,
  Description,
  DryRun,
  NoReboot
}, (err, data) => {
  if (err) {
    console.error(`Error creating image for ${InstanceId}\n`, `${err.message}\n`, err.stack);
    process.exit(1);
  }

  console.log(`Successfully created image of ${InstanceId}`, data);
  process.exit(0);
});
