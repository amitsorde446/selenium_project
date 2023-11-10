import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request
import urllib.parse


def emailsending(rec_em, refid, tm):
    print('email initiated')

    if rec_em != '':
        # sender_email = "prernasingh730@gmail.com"
        sender_email = "info@scoreme.in"
        receiver_email = rec_em
        subject = "ScoreMe Login Info"
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = subject

        url = f"https://lcna326sf2.execute-api.ap-south-1.amazonaws.com/devenv/otplinkformfetch?refid={refid}"

        html = """<html>
        <head>
        <title>GST Anayzer</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link href="https://fonts.googleapis.com/css?family='Montserrat',sans-serif:100,300,400,500,600,700"rel="stylesheet">
        <link href="https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css" rel="stylesheet" integrity="sha384-wvfXpqpZZVQGK6TAh5PVlGOfQNHSoD2xbE+QkPxCAFlNEevoEH3Sl0sibVcOQVnN" crossorigin="anonymous">
        <link rel="stylesheet"href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">
        </head>
        <body>
        <div style="padding: 0px; margin: 0px">
        <divstyle="margin: 0; padding: 30px; background-color: #f9f9f9; width: 830px">
        <table style="padding: 15px; width: 100%; border-collapse: collapse">
        <tbody>
        <tr style="margin: 0px; padding: 0px"></tr>
        <tr style="margin: 0px; padding: 0px">
        <td style="background-color: #f2f2f2;">
        <div>
        <img src="https://app.scoreme.in/assets/images/logo.png" width="15%" style="padding-top: 10px;padding-left: 20px;float: left;padding-bottom: 14px;">
        <p style="color: #797979;; font-family: 'Montserrat',sans-serif; font-size: 12px; text-align: right; padding-top: 15px; padding-right: 20px;">visit: <span style="color: #0057ff; font-family: 'Montserrat',sans-serif; font-size: 12px; font-weight: 600">www.scoreme.in</span></p>
        </div>
        </td>
        </tr>
        <tr style="margin: 0px; padding: 0px">
        <td style="margin: 0px; padding: 15px; background-color: #fff">
        <p style="font-family: 'Montserrat',sans-serif; font-size: 13px; font-weight: normal; color: #636161; text-align: left; padding-top: 10px; padding-left: 20px">Dear User,</p>
        <p style="font-family: 'Montserrat',sans-serif; font-size: 13px; font-weight: normal; color: #636161; text-align: left; padding-top: 10px; padding-left: 20px; padding-right: 10px">This email has been sent by ScoreMe to you. You can click on the link below to submit the OTP. 


        </p>
        <p style="font-family: 'Montserrat',sans-serif; font-size: 13px; font-weight: normal; color: #636161; text-align: left; padding-top: 10px; padding-left: 20px; padding-right: 10px"> <a href=""" + url + """>Click here</a> for link.The link is valid for """ + tm + """ seconds</p>
        <p style="font-family: 'Montserrat',sans-serif; font-size: 13px; font-weight: normal; color: #636161; text-align: left; padding-top: 10px; padding-left: 20px; padding-right: 10px">We thank you for providing us with an opportunity to serve you.</p>
        <p style="font-family: 'Montserrat',sans-serif; font-size: 13px; font-weight: normal; color: #636161; text-align: left; padding-top: 10px; padding-left: 20px; padding-right: 10px">Please feel free to connect to us at the following address support@scoreme.in if you have any queries.
        </p>
        <p style="font-family: 'Montserrat',sans-serif; font-size: 12px; font-weight: normal; color: #636161; text-align: left; padding-top: 10px; padding-left: 20px">Best Regards, <br>ScoreMe Team.</p>
        <p style="font-family: 'Montserrat',sans-serif; font-size: 11px; font-weight: 300; color: #636161; text-align: left; padding-top: 10px; padding-left: 20px; padding-right: 10px">This is a system generated e-mail and please do not reply. Add info@scoreme.in to your white list / safe sender list else, your mailbox filter or ISP (Internet Service Provider) may stop you from receiving e-mails.</p>
        </td>
        </tr>
        <tr style="margin: 0px; padding: 0px">
        <td style="margin: 0px; padding: 15px; padding-bottom: 0px; background-color: #f2f2f2">
        <div style="width: 100%">
        <p style="padding-left: 20px; float: left; font-family: 'Montserrat',sans-serif; font-size: 12px; text-align: left; color: #0057ff; font-weight: 600;">www.scoreme.in <br>info@scoreme.in</p>
        <ul style="list-style: none; float: right; padding-top: 5px;">
        <li style="display: inline-block; padding-right: 5px;"><img src="http://www.easemyretail.com/emailer_emg2017/easemygst-emailer/in.png" style="height: 15px;"/></li>
        <li style="display: inline-block; padding-right: 5px;"><img src="http://www.easemyretail.com/emailer_emg2017/easemygst-emailer/twitter.png" style="height: 15px;"/></li>
        <li style="display: inline-block; padding-right: 5px;"><img src="http://www.easemyretail.com/emailer_emg2017/easemygst-emailer/blog.png" style="height: 15px;"/></li>
        <li style="display: inline-block; padding-right: 5px;"><img src="http://www.easemyretail.com/emailer_emg2017/easemygst-emailer/fb.png" style="height: 15px;"/></li>
        </ul>
        </div>
        </td>
        </tr>
        <tr style="margin: 0px; padding: 0px">
        <td style="margin: 0px; padding: 5px; background-color: #f2f2f2">
        <p style="color: #4a4a4a; text-align: center;margin: -33px !important;font-size: 10px; margin: 0px;">Copyright  ScoreMe 2020, All Rights Reserved.</p>
        </td>
        </tr>
        <tr style="margin: 0px; padding: 0px">
        <td style="margin: 0px; padding-top: 15px">
        <div style="text-align: left">
        <p style="color: #797979; font-weight: normal; font-family: 'Montserrat',sans-serif; font-size: 12px; padding-right: 10px">Please do not print this email unless it is absolutely necessary.</p>
        <p style="color: #797979; font-weight: normal; font-family: 'Montserrat',sans-serif; font-size: 12px; margin: 0px;">***</p>
        <p style="color: #797979; font-weight: normal; font-family: 'Montserrat',sans-serif; font-size: 12px; padding-right: 10px">
        <span style="color: #797979; font-family: 'Montserrat',sans-serif; font-size: 13px;">
        DISCLAIMER:</span>This message and any attachment is confidential and may be privileged or otherwise protected from disclosure. If you are not an intended recipient, please notify the sender and delete this message and any attachment immediately. If you are not an intended recipient you must not copy this message or attachment or disclose the contents to any other person. Unless otherwise specifically stated, no legally binding commitments are created by this email. Any opinions expressed in this message are those of the author and do not necessarily reflect the opinions of anyone else.</p>
        <p style="color: #797979; font-weight: normal; font-family: 'Montserrat',sans-serif; font-size: 12px; padding-right: 10px">
        <span style="color: #797979; font-family: 'Montserrat',sans-serif; font-size: 13px;">
        WARNING:</span>
        Computer viruses can be transmitted via email. The recipient should check this email and any attachments for the presence of viruses. The company accepts no liability for any damage caused by any virus transmitted by this email.</p>
        <p style="color: #797979; font-weight: normal; font-family: 'Montserrat',sans-serif; font-size: 12px; margin: 0px;">***</p>
        </div>
        </td>
        </tr>
        </tbody>
        </table>
        </div>
        </div>
        </body>
        </html>

        """

        message.attach(MIMEText(html, "html"))

        s = smtplib.SMTP()
        # server='email-smtp.ap-south-1.amazonaws.com'
        server = 'email-smtp.us-east-1.amazonaws.com'
        port = 587
        s.connect(server, port)
        s.starttls()
        # username='AKIASUQVYOZ23XGNNKWU'
        username = 'AKIAJZ2TZJH5IROXYOOQ'
        # password='BIsLQj9T9mU8E6EBpJtkoFVgRDaeO83kHXkqifV4po8w'
        password = 'Avnvbm8l0O//qsID0tTPawCsB/H/RCrUt0sYNnf+woyn'
        s.login(username, password)

        s.sendmail(sender_email, receiver_email, message.as_string())
        print('email sent')


def sendSMS(apikey, numbers, sender, message):
    data = urllib.parse.urlencode({'apikey': apikey, 'numbers': numbers,
                                   'message': message, 'sender': sender})
    data = data.encode('utf-8')
    request = urllib.request.Request("https://api.textlocal.in/send/?")
    f = urllib.request.urlopen(request, data)
    fr = f.read()
    return (fr)


def msgsending(rec_m, refid, tm):
    if rec_m != '':
        url = f"https://sii4tklpse.execute-api.ap-south-1.amazonaws.com/devenv/otplinkformfetch?refid={refid}"
        resp = sendSMS('VEv3L2lMkyI-s8UsWJZWeITuBRHY0KjLaAITZ3lQ8Y', rec_m,
                       'SCORME',
                       f"This link is shared by SCOREME to you for providing the GST Username %26 Password for GSTN XYZ. Click {url} Valid for {tm} mins.")
