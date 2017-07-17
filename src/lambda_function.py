import imp
import os
import requests
import urllib
import json
import boto3
import pprint


with open(os.path.join(os.path.dirname(__file__), 'SLACK_TEAM_TOKEN')) as f:
    incoming_token = f.read().strip()

config = None
# load config file
if os.path.isfile("./jarvisbutler.config"):
    with open("jarvisbutler.config") as f:
        config = json.load(f)

slack_channel = '#general'
slack_response_url = None
query = None

def _formparams_to_dict(s1):
    """ Converts the incoming formparams from Slack into a dictionary. Ex: 'text=votebot+ping' """
    retval = {}
    for val in s1.split('&'):
        k, v = val.split('=')
        retval[k] = v
    return retval

def lambda_handler(event, context):
    
    #config file
    pprint.pprint(config)

    # Lambda entry point
    param_map = _formparams_to_dict(event['formparams'])
    text = param_map['text'].split('+')
    global query
    query = urllib.unquote(" ".join(text))
    global slack_channel
    slack_channel = param_map['channel_id']
    retval = None

    global slack_response_url
    slack_response_url = param_map['response_url']
    slack_response_url = urllib.unquote(slack_response_url)

    print "LOG: The request came from: " + slack_channel
    print "LOG: The request is: " + str(text)
    print "LOG: The requesting user is: " + param_map['user_name']

    if  param_map['token'] != incoming_token:  # Check for a valid Slack token
        send_message_to_slack(retval)
    else:
        try:
            #The boto calls in the compare command cause long wait times, so this processing
            # message is sent to notify the requester
            send_message_to_slack("I'm processing your request, please stand by")

            #call sns topic now
            awsKeyId = None
            awsSecretKey = None
            awsSessionToken = None
            session = boto3.session.Session(aws_access_key_id=awsKeyId,aws_secret_access_key=awsSecretKey,aws_session_token=awsSessionToken)
            client = session.client("sns", region_name=config["general"]["region"])
            response = client.publish(
                TopicArn=config["general"]["JarvisButler_arn"],
                Message=str(event)
            )
        except Exception as e:
            post_to_slack("Unable to call jarvis, try again")
            print 'Error: ' + format(str(e))


#function to send processing request message
def send_message_to_slack(val):
    try:
        payload = {
            "text": val,
            "response_type": "ephemeral"
        }
        r = requests.post(slack_response_url, json=payload)
    except Exception as e:
        print "ephemeral_message_request error " + str(e)


def post_to_slack(val):
    if isinstance(val, basestring):
        payload = {
        "text": query + "\n" + val,
        "response_type": "ephemeral"
        }
        r = requests.post(slack_response_url, json=payload)
    else:
        payload = {
        "text": query,
        "attachments": val,
        "response_type": "ephemeral"
        }
        r = requests.post(slack_response_url, json=payload)


def send_to_slack(val, sendto_slack_channel, sender_address, incoming_webhook):
    # this gives easy access to incoming webhook
    #sendto_webhook = get_incoming_webhook()
    sendto_webhook = incoming_webhook

    sendto_slack_channel = urllib.unquote(sendto_slack_channel)

    #information stating requester of data
    sender_title = urllib.unquote(sender_address) + " has requested this information from J.A.R.V.I.S.\n"

    if isinstance(val, basestring):
        try:
            payload = {
                "text": query + "\n" + val,
                "response_type": "ephemeral"
            }
            r = requests.post(slack_response_url, json=payload)
        except Exception as e:
            print "ephemeral_message_request error "+str(e)

        try:
            #send to another slack channel
            if sendto_slack_channel:
                # creating json payload
                payload = {
                    'text': sender_title + '_' + query + '_'+ "\n" + val,
                    'as_user': False,
                    "channel": sendto_slack_channel,
                    'mrkdwn': 'true'
                }
                incoming_message_request = requests.post(sendto_webhook, json=payload)

                #if the slack message was not posted then send a message to sender
                if incoming_message_request.status_code != 200:
                    print (
                        'In send_to_slack ephemeral Slack returned status code %s, the response text is %s' % (
                            incoming_message_request.status_code, incoming_message_request.text)
                    )


                    send_message_to_slack('Unable to execute sendto command, retry with a valid  user or channel')

        except Exception as e:
            print "sendto_message_request error " + str(e)
    else:
        try:
            payload = {
                "text": query,
                "attachments": val,
                "response_type": "ephemeral"
            }
            ephemeral_message_request = requests.post(slack_response_url, json=payload)
        except Exception as e:
            print "ephemeral_message_request error "+str(e)

        # after sending a message to your currenet channel,
        #  then send another to the desired slack channel

        # creating json payload
        try:
            if sendto_slack_channel:
                payload = {
                    'text': sender_title +'_' + query + '_',
                    'as_user': False,
                    "channel": sendto_slack_channel,
                    "attachments": val,
                    'mrkdwn': 'true'
                }

                incoming_message_request = requests.post(sendto_webhook, json=payload)

                # if the slack message was not posted then send a message to sender
                if incoming_message_request.status_code != 200:
                    print (
                        'In send_to_slack ephemeral Slack returned status code %s, the response text is %s' % (
                            incoming_message_request.status_code, incoming_message_request.text)
                    )


                    send_message_to_slack('Unable to execute sendto command, retry with a valid user or channel')

        except Exception as e:
            print "sendto_message_request error "+str(e)
