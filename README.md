# **The Document**

## **Week 1 - Brainstorming**

### Project Description
This project aims to develop an efficient charity platform that uses the process of matching donations with recipients' needs. The system categorises requests from individuals in need, allowing donated items to be sorted accordingly. When a donation matches a recipient's requirements, the platform automatically notifies the recipient, enabling them to collect the item at a designated location. This approach improves the efficiency and effectiveness of our charity giving by ensuring that donations reach those who need them most in a timely manner.

### Functional Requirements
- Users should be able to register into the website with a username and passwords and also they should be able to login with that credentials if in the case where they log out
- Users should be able to locate the position of interest where they can collect their donations/be able to donate their items
- Users should be able to identify what they are in need so that they get pinged when their item is available

### Non-Functional Requirements
- Website should be able to load within 1.5s
- All passwords should be encrypted for increased security also locations of users should be encrypted as well in case of a data leak
- The system should be able to handle at least 1000+ people at the same time without slowing down


## **Week 2 - Creating framework for the website**
|Aspect of Design|Description|
|--------------------|----------------------------------|
|Landing/Home page|The home page should display the logo and website name, along with the ability to navigate to different areas of the website such as donate, login/sign up,etc. It also should have to ability to swap the login with the user profile when the user is logged in, the page should also have description of the company's goal/purpose|
|Donate Page|This page is primarily for informing the donaters on why they should donate and the impacts of donating their items to help the needy, it also should display an interactive google maps displaying where the company HQ is, it also has description on becoming an volunteer since the company is a non-profit company.|
|Login/Signup Page|This page is aimed at registering an user, it requires the user to provide an email, name and password (encrypted) to sign up to the website, the purpose of this is to make sure that there is a way to identify the user when they are collecting or donating items, it also makes sure that there are no one that is making multiple accounts to leech off the generocity of the company.|
|Colour palette|Primarily: Grey. Secondary:White. Other colours: Orange|
|Other pages|Profile page, Request items page, donation 'points' page, top donaters (weekly, monthly). These are the pages that are not included in the framework.|

### Images of framework

**Home Page**

![](Home.png)

**Donate Page**

![](Donate.png)

**Login Page**

![](Login.png)


## **Week 3 - Alternate Designs**

| Aspect of Design | Description |
|------------------|-------------|
| Overall Theme | Warm, welcoming, and calming design with a blocky yet rounded font to create a sense of security. |
| Home Page | Added extra navigation buttons at the top for easier navigation. Included a "stories" section for users to share their experiences. ![](Alt-Home.png) |
| Donate Page | Simplified layout focusing on explaining the donation process. Introduced a universal yellow placeholder at the top across the website. ![](Alt-Donate.png) |
| Login Page | Removed borders and enlarged the font for better accessibility. ![](Alt-Login.png) |
| Flow Diagram | Visual representation of the user flow and background processes triggered by user actions. ![](Flow-Of-Data.png) |

## **Week 4 - Designing Algorithms**

### Designing an algorithm for one functional component

#### **Pseudocode**

#### Part 1: Donation Submission
1. Declare variables: `session_token`, `donation_data`, `donation_id`, `candidates`, `best_match`, `match_id`, `recipient_response`

2. Prompt user to log in and enter donation details (title, category, condition, quantity, location, availability, images)

3. Get `session_token` and `donation_data`

4. IF `session_token` is invalid THEN
- 4.1. Display error message: "Authentication required"
- 4.2. Prompt user to log in again
- 4.3. Get new `session_token`

5. ENDIF

6. IF any required field in `donation_data` is missing (e.g., title, category, location) THEN
- 6.1. Display error message: "Missing required information"
- 6.2. Prompt user to re-enter donation details
- 6.3. Get updated `donation_data`

7. ENDIF

8. Normalise `donation_data` (trim text, validate categories)

9. Store donation in database with `status = PENDING_MATCH` and get `donation_id`

#### Part 2: Matching Process
10. Search for matching recipients in database where category matches and location is within allowed radius
11. IF `candidates` list is empty THEN
- 11.1. Queue `donation_id` for later matching attempts
- 11.2. Display message: "Donation saved. We’ll notify you when a match is found."
12. ELSE
- 12.1. Score each candidate based on category match, distance, urgency, quantity, and trust rating
- 12.2. Select `best_match` with highest score
- 12.3. Create match record linking `donation_id` and `best_match.id`, set status = `PENDING_CONFIRMATION`, and get `match_id`
- 12.4. Send notification to recipient with match details
- 12.5. Send notification to donor that a match is pending recipient confirmation
- 12.6. Display message: "Match found! Waiting for recipient confirmation."
13. ENDIF

#### Part 3: Recipient Confirmation
14. Wait for `recipient_response` (Accept or Decline) from notification link
15. IF `recipient_response` = Accept THEN
- 15.1. Verify that donation is still available and not expired
- 15.2. Update match status = `CONFIRMED`
- 15.3. Update donation status = `MATCHED_CONFIRMED`
- 15.4. Notify donor to arrange pickup or delivery
16. ELSE IF `recipient_response` = Decline THEN
- 16.1. Update match status = `DECLINED`
- 16.2. Update donation status = `PENDING_MATCH`
- 16.3. Return to Step 10 to search for a new match
17. ENDIF

#### Part 4: Handover and Completion
18. When both donor and recipient confirm logistics, set donation status = `IN_TRANSIT` or `READY_FOR_PICKUP`
19. After item is received, recipient confirms delivery via system
20. Update donation status = `COMPLETED`
21. Update match status = `COMPLETED`
22. Prompt donor and recipient for feedback and store ratings
23. Log event in system for analytics
24. Display final message: "Donation successfully completed."

### Design 2 Test Cases
**Test Case 1**

Test Case ID: A unique identifier for easy reference.
Test Case Name: A short, descriptive title of what’s being tested.
Preconditions: Any setup or initial conditions that must be met before testing begins.
Test Steps:
Clear, step-by-step instructions on how to execute the test.
Expected Result: What should happen after performing the test steps.
Actual Result: What actually happens during testing (filled out after execution).
Pass/Fail: A simple indication of whether the test succeeded or failed.
Priority: Helps categorise the importance of the test.

**Test Case 2**

Test Case ID: A unique identifier for easy reference.
Test Case Name: A short, descriptive title of what’s being tested.
Preconditions: Any setup or initial conditions that must be met before testing begins.
Test Steps:
Clear, step-by-step instructions on how to execute the test.
Expected Result: What should happen after performing the test steps.
Actual Result: What actually happens during testing (filled out after execution).
Pass/Fail: A simple indication of whether the test succeeded or failed.
Priority: Helps categorise the importance of the test.