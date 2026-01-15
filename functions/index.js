const functions = require('firebase-functions');
const admin = require('firebase-admin');
const nodemailer = require('nodemailer');
const cors = require('cors')({ origin: true });

// Initialize Firebase Admin
admin.initializeApp();

// Create reusable transporter object using SMTP
const transporter = nodemailer.createTransport({
  service: 'gmail',
  auth: {
    user: functions.config().gmail.email, // Set via: firebase functions:config:set gmail.email="sibiyan4444@gmail.com"
    pass: functions.config().gmail.password // Set via: firebase functions:config:set gmail.password="your-app-password"
  }
});

// Cloud Function: Send welcome email when subscriber is added
exports.sendWelcomeEmail = functions.firestore
  .document('subscribers/{subscriberId}')
  .onCreate(async (snap, context) => {
    const subscriber = snap.data();
    const email = subscriber.email;
    const subscriberId = context.params.subscriberId;

    if (!email) {
      console.error('No email found for subscriber:', subscriberId);
      return null;
    }

    // Check if email was already sent
    if (subscriber.emailSent) {
      console.log('Email already sent for:', email);
      return null;
    }

    const mailOptions = {
      from: `"Mzansi Insights" <sibiyan4444@gmail.com>`,
      to: email,
      subject: `Welcome to Mzansi Insights! 🎉`,
      html: `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="UTF-8">
          <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }
            .content { padding: 30px; background: #f9f9f9; }
            .footer { background: #333; color: white; padding: 20px; text-align: center; }
            .button { display: inline-block; padding: 12px 30px; background: #3b82f6; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 15px 0; }
            .features { margin: 20px 0; }
            .feature-item { margin: 10px 0; padding-left: 20px; position: relative; }
            .feature-item:before { content: "✓"; color: #10b981; font-weight: bold; position: absolute; left: 0; }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>Mzansi Insights 🇿🇦</h1>
            <p>Your trusted source for South African news & opportunities</p>
          </div>
          <div class="content">
            <h2>Welcome Aboard!</h2>
            <p>Hello,</p>
            <p>Thank you for subscribing to <strong>Mzansi Insights</strong>! We're excited to have you join our community of informed South Africans.</p>
            
            <div class="features">
              <p><strong>What you'll receive:</strong></p>
              <div class="feature-item">Latest South African news updates</div>
              <div class="feature-item">Job opportunities and career tips</div>
              <div class="feature-item">Grant and SASSA information</div>
              <div class="feature-item">Business and investment news</div>
              <div class="feature-item">Technology and entertainment updates</div>
              <div class="feature-item">Sports and lifestyle content</div>
            </div>
            
            <p>We're committed to bringing you the most relevant and timely information to help you stay informed and make better decisions.</p>
            
            <div style="background: #e8f4fc; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #3b82f6;">
              <p><strong>💡 Pro Tip:</strong> Add <strong>sibiyan4444@gmail.com</strong> to your contacts to ensure our emails land in your inbox.</p>
            </div>
            
            <p>If you have any questions or need assistance, don't hesitate to contact us:</p>
            <p>📧 Email: <a href="mailto:sibiyan4444@gmail.com">sibiyan4444@gmail.com</a></p>
            <p>📞 Phone: <strong>072 472 8166</strong></p>
            
            <p>Best regards,<br>
            <strong>The Mzansi Insights Team</strong></p>
          </div>
          <div class="footer">
            <p>&copy; ${new Date().getFullYear()} Mzansi Insights. All rights reserved.</p>
            <p><small>This email was sent to ${email}</small></p>
          </div>
        </body>
        </html>
      `
    };

    try {
      // Send email
      await transporter.sendMail(mailOptions);
      console.log('Welcome email sent to:', email);

      // Update Firestore document
      await snap.ref.update({
        emailSent: true,
        emailSentAt: admin.firestore.FieldValue.serverTimestamp(),
        status: 'confirmed'
      });

      return null;
    } catch (error) {
      console.error('Error sending email:', error);
      
      // Update with error status
      await snap.ref.update({
        emailError: error.message,
        emailStatus: 'failed'
      });

      throw error;
    }
  });

// HTTP Cloud Function for direct subscription
exports.subscribe = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    // Only allow POST requests
    if (req.method !== 'POST') {
      return res.status(405).send('Method Not Allowed');
    }

    try {
      const { email } = req.body;
      
      if (!email) {
        return res.status(400).json({ 
          success: false, 
          error: 'Email is required' 
        });
      }

      // Validate email format
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        return res.status(400).json({ 
          success: false, 
          error: 'Invalid email format' 
        });
      }

      // Check if email already exists
      const existing = await admin.firestore()
        .collection('subscribers')
        .where('email', '==', email)
        .get();

      if (!existing.empty) {
        return res.status(409).json({ 
          success: false, 
          error: 'Email already subscribed' 
        });
      }

      // Create new subscriber
      const subscriberData = {
        email: email,
        subscribedAt: admin.firestore.FieldValue.serverTimestamp(),
        status: 'pending',
        source: 'website_form',
        emailSent: false
      };

      const subscriberRef = await admin.firestore()
        .collection('subscribers')
        .add(subscriberData);

      return res.status(200).json({ 
        success: true, 
        message: 'Subscription successful. Welcome email will be sent shortly.',
        subscriberId: subscriberRef.id 
      });

    } catch (error) {
      console.error('Subscription error:', error);
      return res.status(500).json({ 
        success: false, 
        error: 'Internal server error' 
      });
    }
  });
});

// HTTP Cloud Function to send test email
exports.sendTestEmail = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    if (req.method !== 'POST') {
      return res.status(405).send('Method Not Allowed');
    }

    const { to, name } = req.body;

    const mailOptions = {
      from: `"Mzansi Insights" <sibiyan4444@gmail.com>`,
      to: to || 'sibiyan4444@gmail.com',
      subject: `Test Email from Mzansi Insights`,
      html: `
        <h2>Test Email Successful! ✅</h2>
        <p>This is a test email from Mzansi Insights Cloud Functions.</p>
        <p>If you're receiving this, your email setup is working correctly.</p>
        <p><strong>Sender:</strong> sibiyan4444@gmail.com</p>
        <p><strong>Phone:</strong> 072 472 8166</p>
        <p><strong>Time:</strong> ${new Date().toLocaleString()}</p>
      `
    };

    try {
      await transporter.sendMail(mailOptions);
      res.status(200).json({ 
        success: true, 
        message: 'Test email sent successfully' 
      });
    } catch (error) {
      console.error('Test email error:', error);
      res.status(500).json({ 
        success: false, 
        error: error.message 
      });
    }
  });
});

// HTTP Cloud Function to get subscriber count
exports.getSubscriberCount = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    try {
      const snapshot = await admin.firestore()
        .collection('subscribers')
        .get();
      
      res.status(200).json({ 
        success: true, 
        count: snapshot.size 
      });
    } catch (error) {
      console.error('Count error:', error);
      res.status(500).json({ 
        success: false, 
        error: error.message 
      });
    }
  });
});