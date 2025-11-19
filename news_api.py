# pip install langchain-community==0.3.29
# pip install requests==2.31.0
# pip install sentence-transformers==2.2.2
# pip install langchain-community-0.3.29
# pip install langchain-openai==0.3.33 
# pip install langchain-core==0.3.76
# pip install requests==2.32.5
# pip install scikit-learn==1.71
# 


import requests
import os
import json
from datetime import datetime, timedelta
import time
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_openai.embeddings import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np



# Configuration
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

class LinkedInAuth:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
    def save_tokens_to_env(self, access_token, refresh_token=None, expires_in=3600):
        """Save tokens to environment or file for reuse"""
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        # Save to environment variables (for current session)
        os.environ['LINKEDIN_ACCESS_TOKEN'] = access_token
        if refresh_token:
            os.environ['LINKEDIN_REFRESH_TOKEN'] = refresh_token
            
        # Save to file for persistence across runs
        token_data = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None
        }
        
        try:
            with open('.linkedin_tokens.json', 'w') as f:
                json.dump(token_data, f)
            print("✅ Tokens saved to .linkedin_tokens.json")
        except Exception as e:
            print(f"⚠️  Could not save tokens to file: {e}")
    
    def load_tokens_from_storage(self):
        """Load existing tokens from environment or file"""
        # Try environment variables first
        access_token = os.getenv('LINKEDIN_ACCESS_TOKEN')
        refresh_token = os.getenv('LINKEDIN_REFRESH_TOKEN')
        
        if access_token:
            print("📁 Found tokens in environment variables")
            self.access_token = access_token
            self.refresh_token = refresh_token
            return True
            
        # Try loading from file
        try:
            with open('.linkedin_tokens.json', 'r') as f:
                token_data = json.load(f)
                
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            
            if token_data.get('expires_at'):
                self.token_expires_at = datetime.fromisoformat(token_data['expires_at'])
                
            if self.access_token:
                print("📁 Found tokens in .linkedin_tokens.json")
                return True
                
        except (FileNotFoundError, json.JSONDecodeError):
            print("📁 No existing tokens found")
            
        return False
    
    def is_token_expired(self):
        """Check if the current token is expired"""
        if not self.token_expires_at:
            return False  # Unknown expiry, assume valid
            
        return datetime.now() >= self.token_expires_at - timedelta(minutes=5)  # 5 min buffer
    
    def refresh_access_token(self):
        """Use refresh token to get a new access token"""
        if not self.refresh_token:
            print("❌ No refresh token available")
            return False
            
        print("🔄 Refreshing access token...")
        
        token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            self.save_tokens_to_env(
                token_data['access_token'],
                token_data.get('refresh_token', self.refresh_token),  # Keep old refresh token if new not provided
                token_data.get('expires_in', 3600)
            )
            print("✅ Access token refreshed successfully!")
            return True
        else:
            print(f"❌ Token refresh failed: {response.status_code} - {response.text}")
            return False
    
    def validate_token(self):
        """Test if current access token is valid"""
        if not self.access_token:
            return False
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        response = requests.get('https://api.linkedin.com/v2/userinfo', headers=headers)
        
        return response.status_code == 200
    
    def get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        
        # Load existing tokens
        self.load_tokens_from_storage()
        
        # If we have a token, check if it's valid
        if self.access_token:
            if self.validate_token():
                print("✅ Existing token is valid")
                return self.access_token
            else:
                print("⚠️  Existing token is invalid")
                
        # If token is expired or invalid, try to refresh
        if self.refresh_token:
            if self.refresh_access_token():
                return self.access_token
        
        # If all else fails, need manual authorization
        print("❌ No valid token available. Manual authorization required.")
        return None
    
    def manual_authorization_flow(self):
        """Perform manual authorization (one-time setup)"""
        print("\n🔐 MANUAL AUTHORIZATION REQUIRED")
        print("=" * 50)
        print("This is a ONE-TIME setup. Tokens will be saved for future automation.")
        print()
        
        from requests_oauthlib import OAuth2Session
        from urllib.parse import urlparse, parse_qs
        
        redirect_uri = 'https://www.linkedin.com/developers/tools/oauth/redirect'
        scope = ["openid", "profile", "email", "w_member_social"]
        
        # Generate authorization URL
        oauth = OAuth2Session(self.client_id, redirect_uri=redirect_uri, scope=scope)
        authorization_url, state = oauth.authorization_url('https://www.linkedin.com/oauth/v2/authorization')
        
        print(f"1. Visit this URL: {authorization_url}")
        print("2. Authorize your application")
        print("3. Copy the full callback URL")
        
        callback_url = input("\nPaste the callback URL here: ")
        
        # Extract authorization code
        parsed_url = urlparse(callback_url)
        auth_code = parse_qs(parsed_url.query).get('code', [None])[0]
        
        if not auth_code:
            print("❌ No authorization code found")
            return False
        
        # Exchange for tokens
        token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
        token_data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        response = requests.post(token_url, data=token_data)
        
        if response.status_code == 200:
            token_response = response.json()
            self.save_tokens_to_env(
                token_response['access_token'],
                token_response.get('refresh_token'),
                token_response.get('expires_in', 3600)
            )
            print("✅ Authorization successful! Tokens saved for future use.")
            return True
        else:
            print(f"❌ Token exchange failed: {response.status_code} - {response.text}")
            return False

def get_user_profile(access_token):
    """Get user profile using the /userinfo endpoint"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get('https://api.linkedin.com/v2/userinfo', headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Profile fetch failed: {response.status_code} - {response.text}")
        return None

def create_draft_linkedin_post():
    """Create a draft LinkedIn post content using AI and news data"""
    
    print("🔍 Fetching news articles...")
    
    # 1️⃣ Setup LLM + embeddings
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.3)
    embed_model = OpenAIEmbeddings(model="text-embedding-3-small")

    # 2️⃣ Fetch Top Headlines
    url1 = "https://newsapi.org/v2/top-headlines"
    params1 = {"country": "us", "pageSize": 50, "apiKey": NEWSAPI_KEY}
    
    try:
        top_response = requests.get(url1, params=params1)
        top = top_response.json()["articles"]
        top_titles = [a["title"] for a in top if a["title"]]
    except Exception as e:
        print(f"❌ Error fetching top headlines: {e}")
        fallback_headline = "Technology and Innovation Update"
        return "💡 Just learned something new that I wanted to share with my network.", fallback_headline

    # 3️⃣ Fetch Popular Articles
    url2 = "https://newsapi.org/v2/everything"
    params2 = {
        "q": "data science OR machine learning OR technology OR AI OR finance OR economy OR baseball statistics",
        "language": "en",
        "sortBy": "popularity",
        "pageSize": 50,
        "from": (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
        "apiKey": NEWSAPI_KEY
    }
    
    try:
        popular_response = requests.get(url2, params=params2)
        popular = popular_response.json()["articles"]
        popular_titles = [a["title"] for a in popular if a["title"]]
    except Exception as e:
        print(f"❌ Error fetching popular articles: {e}")
        fallback_headline = "Business and Market Developments"
        return "🚀 Exciting developments in tech today! The future is looking bright.", fallback_headline

    # ✅ Safety check
    if not top_titles or not popular_titles:
        print("⚠️ No articles fetched. Using fallback content.")
        fallback_headline = "Professional Development and Growth"
        return "🌟 Reflecting on the journey so far and looking forward to what's next.", fallback_headline

    print(f"📊 Fetched {len(top_titles)} top headlines and {len(popular_titles)} popular articles")

    # 4️⃣ Embeddings
    try:
        top_emb = embed_model.embed_documents(top_titles)
        pop_emb = embed_model.embed_documents(popular_titles)
    except Exception as e:
        print(f"❌ Error creating embeddings: {e}")
        fallback_headline = "Professional Growth and Development"
        return "💼 Professional growth comes from continuous learning and adaptation.", fallback_headline

    # 5️⃣ Cosine similarity between Top vs Popular
    cosine_scores = cosine_similarity(np.array(top_emb), np.array(pop_emb))

    threshold = 0.25
    matches = []
    for i, top_title in enumerate(top_titles):
        for j, pop_title in enumerate(popular_titles):
            score = cosine_scores[i][j]
            if score > threshold:
                matches.append((score, top_title, pop_title))

    # 6️⃣ Find best match
    if not matches:
        print("⚠️ No similar headlines found. Using fallback content.")
        fallback_headline = "Goals and Motivation"
        return "🎯 Setting new goals and pushing boundaries. What's motivating you today?", fallback_headline

    matches = sorted(matches, key=lambda x: x[0], reverse=True)
    print(f"🔥 Found {len(matches)} similar headlines")

    # ✅ Pick best headline automatically
    score, top_title, best_match = matches[0]  # top similarity 
    print(f"🎯 Selected headline (similarity: {score:.2f}): {best_match}")

    # Store the selected headline for return
    selected_headline = best_match

    # ✅ Prompt for LLM
    prompt_template = PromptTemplate.from_template(f"""
    You are an expert historian, philosopher, data scientist, and social media strategist.
    Your task is to transform a modern news headline into a compelling, professional LinkedIn post.

    Constraints for style and tone (MUST follow):
    - ✅ Content must inform, inspire, or teach (career lessons, insights, historical parallels, data-driven commentary).
    - ✅ Posts must tie back to professional identity: data science, machine learning, statistics, coding, AI, finance, decision-making, leadership, or entrepreneurship.
    - ✅ Storytelling is the backbone: lead with a narrative or historical echo, then build the analytical case.
    - ✅ Support with statistics, datasets, or credible studies whenever possible (cite source in plain text).
    - ⚠️ Humor/memes only if clever and relevant; strong opinions must be thoughtful, not polarizing.
    - ❌ No oversharing, rants, lifestyle-only posts, or political attacks. Keep it professional.

    Instructions:
    1. Take this news headline: "{selected_headline}".
    2. Write a short hook: summarize the headline in 1–2 punchy, story-like sentences.
    3. Connect it to a historical event, lesson, or philosophical idea (use narrative to engage).
    4. Layer in a data science or analytical insight (trends, probabilities, or human behavior patterns).
    5. Cite at least one credible statistic, dataset, or study (mention source briefly).
    6. Add a reflective quote (philosophical, leadership, or historical) to deepen the message.
    7. Keep the entire written post in paragraphs.
    8. End with:
    - A disclosure line (e.g., "Follow for more data-driven news wisdom.")
    - A line break.
    - 3–5 smart, relevant hashtags.

    Final output: A polished LinkedIn post ready to publish that is professional, story-driven, historically grounded, and data-informed.
    """)



    try:
        prompt = prompt_template.format(headline=best_match)
        draft_response = llm.invoke(prompt)
        
        # Extract content from the response
        if hasattr(draft_response, 'content'):
            draft_content = draft_response.content
        else:
            draft_content = str(draft_response)
            
        print("✅ AI-generated LinkedIn post created successfully!")
        return draft_content.strip()
        
    except Exception as e:
        print(f"❌ Error generating AI post: {e}")
        fallback_headline = "Innovation and Growth in Today's Market"
        return "🔥 Innovation never stops. Here's what's catching my attention lately."

def automated_linkedin_post(draft_linkedin_post=None):
    """Fully automated LinkedIn posting (after initial setup)"""
    
    # Initialize authentication
    auth = LinkedInAuth(CLIENT_ID, CLIENT_SECRET)
    
    # Get valid token (automated)
    access_token = auth.get_valid_token()
    
    # If no valid token, require manual setup
    if not access_token:
        print("🔧 First-time setup required...")
        if not auth.manual_authorization_flow():
            return False
        access_token = auth.access_token
    
    # Get user profile
    profile = get_user_profile(access_token)
    if not profile:
        return False
        
    person_id = profile['sub']
    print(f"📝 Posting as: {profile.get('name', 'Unknown')} (ID: {person_id})")
    
    # Create the message content
    # if draft_linkedin_post is None:
    #     draft_linkedin_post, selected_headline = create_draft_linkedin_post()
    # else:
    #     selected_headline = "Breaking News Today"  # Fallback if headline not provided
    
    # Get current day of week for headline format
    current_day = datetime.now().strftime('%A')
    day_headlines = {
        'Monday': f"🔥 Hot Off the Press 🔥",
        'Tuesday': f"🤔 What Do You Think? 🤔",
        'Wednesday': f"⚡ Mid-Week Spark ⚡",
        'Thursday': f"🎯 Thursday Thoughts 🎯",
        'Friday': f"🚀 Friday Focus 🚀",
        'Saturday': f"🌟 Weekend Wisdom 🌟",
        'Sunday': f"💡 Sunday Spotlight 💡"
    }
    
    # Get the day-specific headline
    day_headline = day_headlines.get(current_day)
    
    # Create the final message structure
    # timestamp_header = f"🤖 Automated LinkedIn post - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    # final_message = f"{timestamp_header}\n\n{day_headline}\n\n{draft_linkedin_post}"
    final_message = f"{day_headline}\n\n{draft_linkedin_post}"
    
    print(f"📄 Final post content:\n{final_message}\n")
    
    # Create the post
    url = 'https://api.linkedin.com/v2/ugcPosts'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "author": f"urn:li:person:{person_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": final_message},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 201:
        print(f"✅ Successfully posted to LinkedIn!")
        return True
    else:
        print(f"❌ Post failed: {response.status_code} - {response.text}")
        return False

# Main execution function
def main():
    """Main function for automated LinkedIn posting"""
    
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ CLIENT_ID and CLIENT_SECRET environment variables are required")
        return
    
    if not NEWSAPI_KEY or not OPENAI_API_KEY:
        print("❌ NEWSAPI_KEY and OPENAI_API_KEY environment variables are required")
        return
    
    print("🤖 LinkedIn Automated Posting with AI Content Generation")
    print("=" * 60)
    
    # Generate AI-powered content
    print("🧠 Generating AI content...")
    draft_post = create_draft_linkedin_post()
    
    print(f"\n📝 Generated post preview:\n{draft_post}\n")
    
    # Post automatically
    success = automated_linkedin_post(draft_post)
    
    if success:
        print("\n🎉 Automation successful!")
        print("AI-generated content posted to LinkedIn with timestamp!")
        print("Future runs will be fully automated (no manual intervention needed)")
    else:
        print("\n❌ Automation failed")

if __name__ == "__main__":
    main()
