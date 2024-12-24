import logging
from typing import Optional, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from abc import ABC, abstractmethod
from core.config import EmailConfig

logger = logging.getLogger(__name__)

class EmailProvider(ABC):
    """Base class for email providers."""
    
    @abstractmethod
    async def connect(self):
        """Initialize connection to email service."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection to email service."""
        pass
    
    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        html: bool = True
    ):
        """Send an email."""
        pass

class GmailProvider(EmailProvider):
    """Gmail-specific email provider implementation."""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        self._smtp = None
        
    async def connect(self):
        """Initialize SMTP connection for Gmail."""
        try:
            # Close existing connection if any
            if self._smtp:
                try:
                    self._smtp.quit()
                except:
                    pass
                self._smtp = None
            
            # Create new connection
            self._smtp = smtplib.SMTP("smtp.gmail.com", 587)
            self._smtp.starttls()
            self._smtp.login(self.config.username, self.config.password)
            logger.info("Gmail SMTP connection established")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Gmail SMTP: {str(e)}")
            return False
    
    async def disconnect(self):
        """Close SMTP connection."""
        if self._smtp:
            try:
                self._smtp.quit()
                self._smtp = None
                logger.info("Gmail SMTP connection closed")
                return True
            except Exception as e:
                logger.error(f"Error closing Gmail SMTP connection: {str(e)}")
                return False
        return True
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        html: bool = True,
        retries: int = 3
    ):
        """Send an email through Gmail with retries."""
        last_error = None
        for attempt in range(retries):
            try:
                # Always establish a fresh connection
                if not await self.connect():
                    continue
                
                msg = MIMEMultipart()
                msg['From'] = self.config.from_email
                msg['To'] = to_email
                msg['Subject'] = subject
                
                if cc:
                    msg['Cc'] = ', '.join(cc)
                if bcc:
                    msg['Bcc'] = ', '.join(bcc)
                
                content_type = 'html' if html else 'plain'
                msg.attach(MIMEText(body, content_type))
                
                recipients = [to_email]
                if cc:
                    recipients.extend(cc)
                if bcc:
                    recipients.extend(bcc)
                
                self._smtp.send_message(msg, self.config.from_email, recipients)
                logger.info(f"Email sent via Gmail to {to_email}")
                
                # Close connection after sending
                await self.disconnect()
                return True
                
            except Exception as e:
                last_error = e
                logger.warning(f"Email send attempt {attempt + 1} failed: {str(e)}")
                # Try to clean up connection
                await self.disconnect()
                continue
        
        # If we get here, all retries failed
        logger.error(f"Failed to send email via Gmail after {retries} attempts: {str(last_error)}")
        raise last_error

class Office365Provider(EmailProvider):
    """Office 365-specific email provider implementation."""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        self._smtp = None
    
    async def connect(self):
        """Initialize SMTP connection for Office 365."""
        try:
            # Close existing connection if any
            if self._smtp:
                try:
                    self._smtp.quit()
                except:
                    pass
                self._smtp = None
            
            # Create new connection
            self._smtp = smtplib.SMTP("smtp.office365.com", 587)
            self._smtp.starttls()
            self._smtp.login(self.config.username, self.config.password)
            logger.info("Office 365 SMTP connection established")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Office 365 SMTP: {str(e)}")
            return False
    
    async def disconnect(self):
        """Close SMTP connection."""
        if self._smtp:
            try:
                self._smtp.quit()
                self._smtp = None
                logger.info("Office 365 SMTP connection closed")
                return True
            except Exception as e:
                logger.error(f"Error closing Office 365 SMTP connection: {str(e)}")
                return False
        return True
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        html: bool = True,
        retries: int = 3
    ):
        """Send an email through Office 365 with retries."""
        last_error = None
        for attempt in range(retries):
            try:
                # Always establish a fresh connection
                if not await self.connect():
                    continue
                
                msg = MIMEMultipart()
                msg['From'] = self.config.from_email
                msg['To'] = to_email
                msg['Subject'] = subject
                
                if cc:
                    msg['Cc'] = ', '.join(cc)
                if bcc:
                    msg['Bcc'] = ', '.join(bcc)
                
                content_type = 'html' if html else 'plain'
                msg.attach(MIMEText(body, content_type))
                
                recipients = [to_email]
                if cc:
                    recipients.extend(cc)
                if bcc:
                    recipients.extend(bcc)
                
                self._smtp.send_message(msg, self.config.from_email, recipients)
                logger.info(f"Email sent via Office 365 to {to_email}")
                
                # Close connection after sending
                await self.disconnect()
                return True
                
            except Exception as e:
                last_error = e
                logger.warning(f"Email send attempt {attempt + 1} failed: {str(e)}")
                # Try to clean up connection
                await self.disconnect()
                continue
        
        # If we get here, all retries failed
        logger.error(f"Failed to send email via Office 365 after {retries} attempts: {str(last_error)}")
        raise last_error

class EmailClient:
    """Client for sending emails."""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        # Initialize the appropriate provider based on configuration
        if config.provider == "gmail":
            self._provider = GmailProvider(config)
        elif config.provider == "office365":
            self._provider = Office365Provider(config)
        else:
            raise ValueError(f"Unsupported email provider: {config.provider}")
    
    async def connect(self):
        """Initialize connection to email service."""
        return await self._provider.connect()
    
    async def disconnect(self):
        """Close connection to email service."""
        return await self._provider.disconnect()
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        html: bool = True
    ):
        """
        Send an email using the configured provider.
        
        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            body (str): Email body content
            cc (List[str], optional): CC recipients
            bcc (List[str], optional): BCC recipients
            html (bool): Whether body is HTML (default True)
        """
        return await self._provider.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            html=html
        )

from core.types import DecisionType

class EmailTemplate:
    """Base class for email templates."""
    
    # Test email recipients
    TEST_EMAIL = "yvoderooij@gmail.com"
    PROD_EMAIL = "Jaap@marktlinkcapital.com"
    
    @staticmethod
    def get_recipients(is_test: bool = True) -> List[str]:
        """Get email recipients based on environment."""
        return [EmailTemplate.TEST_EMAIL] if is_test else [EmailTemplate.PROD_EMAIL]
    
    @staticmethod
    def urgent_follow_up(
        company_name: str,
        summary: str,
        key_points: List[str],
        next_steps: List[str]
    ) -> str:
        """Generate urgent follow-up email template."""
        return f"""
        <h2>Urgent Follow-Up Required: {company_name}</h2>
        
        <h3>Meeting Summary</h3>
        <p>{summary}</p>
        
        <h3>Key Points</h3>
        <ul>
            {''.join(f'<li>{point}</li>' for point in key_points)}
        </ul>
        
        <h3>Next Steps</h3>
        <ul>
            {''.join(f'<li>{step}</li>' for step in next_steps)}
        </ul>
        
        <p><strong>Please review and take action as soon as possible.</strong></p>
        """
    
    @staticmethod
    def fund_not_urgent(
        company_name: str,
        summary: str,
        key_points: List[str],
        next_steps: List[str]
    ) -> str:
        """Generate non-urgent fund follow-up email template."""
        return f"""
        <h2>Fund Follow-Up: {company_name}</h2>
        
        <h3>Meeting Summary</h3>
        <p>{summary}</p>
        
        <h3>Key Points</h3>
        <ul>
            {''.join(f'<li>{point}</li>' for point in key_points)}
        </ul>
        
        <h3>Suggested Next Steps</h3>
        <ul>
            {''.join(f'<li>{step}</li>' for step in next_steps)}
        </ul>
        """
    
    @staticmethod
    def future_fund(
        company_name: str,
        summary: str,
        key_points: List[str],
        next_steps: List[str]
    ) -> str:
        """Generate future fund follow-up email template."""
        return f"""
        <h2>Future Fund Opportunity: {company_name}</h2>
        
        <h3>Meeting Summary</h3>
        <p>{summary}</p>
        
        <h3>Key Points</h3>
        <ul>
            {''.join(f'<li>{point}</li>' for point in key_points)}
        </ul>
        
        <h3>Follow-Up Plan</h3>
        <ul>
            {''.join(f'<li>{step}</li>' for step in next_steps)}
        </ul>
        
        <p>This opportunity has been noted for future fund consideration.</p>
        """
    
    @staticmethod
    def no_action(
        company_name: str,
        summary: str,
        key_points: List[str],
        reasoning: str
    ) -> str:
        """Generate template for opportunities that don't fit current criteria."""
        return f"""
        <h2>Investment Opportunity Review: {company_name}</h2>
        
        <h3>Meeting Summary</h3>
        <p>{summary}</p>
        
        <h3>Key Points</h3>
        <ul>
            {''.join(f'<li>{point}</li>' for point in key_points)}
        </ul>
        
        <h3>Assessment</h3>
        <p>{reasoning}</p>
        
        <p>Based on our current investment criteria and strategy, we will not be pursuing this opportunity further at this time.</p>
        """
    
    @staticmethod
    def get_template_for_decision(decision_type: DecisionType):
        """Maps decision types to appropriate email templates."""
        template_map = {
            DecisionType.FUND_X: EmailTemplate.fund_not_urgent,  # For non-urgent fund decisions
            DecisionType.FOLLOW_UP: EmailTemplate.urgent_follow_up,  # For urgent follow-ups
            DecisionType.FUTURE_FUND: EmailTemplate.future_fund,  # For future fund opportunities
            DecisionType.NO_ACTION: EmailTemplate.no_action,  # For opportunities we're passing on
        }
        return template_map.get(decision_type)
