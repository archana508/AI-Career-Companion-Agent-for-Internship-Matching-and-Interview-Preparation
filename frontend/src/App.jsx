import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API = 'http://localhost:8000'

function App() {
  const [page, setPage] = useState('home')
  const [authMode, setAuthMode] = useState('login')
  const [message, setMessage] = useState('')
  const [loggedIn, setLoggedIn] = useState(false)
  const [loading, setLoading] = useState(false)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [location, setLocation] = useState('')
  const [skills, setSkills] = useState('')

  const [resumeFile, setResumeFile] = useState(null)
  const [resumeAnalyzed, setResumeAnalyzed] = useState(false)

  const [selectedInterviewType, setSelectedInterviewType] = useState(null)
  const [interviewIndex, setInterviewIndex] = useState(0)

  // ==========================================
  // SKILLS
  // ==========================================

  const getSkillsArray = () => {
    return skills
      .split(',')
      .map((skill) => skill.trim())
      .filter(Boolean)
  }

  // ==========================================
  // API RESPONSE
  // ==========================================

  const getResponseData = async (response) => {
    try {
      return await response.json()
    } catch {
      return null
    }
  }

  // ==========================================
  // NAVIGATION
  // ==========================================

  const goTo = (target) => {
    setPage(target)
    setMessage('')
  }

  // ==========================================
  // CHECK EXISTING LOGIN SESSION
  // ==========================================

  useEffect(() => {
    const checkSession = async () => {
      try {
        const response = await fetch(`${API}/auth/me`, {
          method: 'GET',
          credentials: 'include',
          headers: {
            Accept: 'application/json',
          },
        })

        if (!response.ok) {
          setLoggedIn(false)
          return
        }

        const data = await getResponseData(response)

        setLoggedIn(true)

        const user = data?.user || data

        if (user) {
          setName(user.name || '')
          setEmail(user.email || '')
          setLocation(user.location_preference || '')

          if (Array.isArray(user.skills)) {
            setSkills(user.skills.join(', '))
          }
        }
      } catch (error) {
        console.log('No active login session.')
        setLoggedIn(false)
      }
    }

    checkSession()
  }, [])

  // ==========================================
  // SIGNUP
  // ==========================================

  const handleSignup = async (e) => {
    e.preventDefault()

    setLoading(true)
    setMessage('Creating your account...')

    try {
      const response = await fetch(`${API}/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          password,
          location_preference: location.trim(),
          skills: getSkillsArray(),
        }),
      })

      const data = await getResponseData(response)

      if (response.ok) {
        setMessage('✅ Account created successfully! Please login.')
        setAuthMode('login')
        setPassword('')
        return
      }

      if (response.status === 409) {
        setMessage('⚠️ This email is already registered. Please login.')
        setAuthMode('login')
        return
      }

      setMessage(
        `❌ Signup failed${data?.detail ? `: ${data.detail}` : '.'}`
      )
    } catch (error) {
      console.error('Signup error:', error)

      setMessage(
        '❌ Cannot connect to the backend. Make sure FastAPI is running on http://localhost:8000'
      )
    } finally {
      setLoading(false)
    }
  }

  // ==========================================
  // LOGIN
  // ==========================================

  const handleLogin = async (e) => {
    e.preventDefault()

    if (!email.trim() || !password) {
      setMessage('⚠️ Please enter your email and password.')
      return
    }

    setLoading(true)
    setMessage('Logging in...')

    try {
      const response = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      })

      const data = await getResponseData(response)

      console.log('LOGIN STATUS:', response.status)
      console.log('LOGIN DATA:', data)

      if (response.ok) {
        setLoggedIn(true)

        const user = data?.user || data

        if (user) {
          setName(user.name || '')
          setEmail(user.email || email.trim())
          setLocation(user.location_preference || '')

          if (Array.isArray(user.skills)) {
            setSkills(user.skills.join(', '))
          }
        }

        setPassword('')
        setMessage('✅ Login successful!')
        setPage('profile')

        return
      }

      if (response.status === 401) {
        setLoggedIn(false)

        setMessage(
          `❌ Invalid email or password${
            data?.detail ? `: ${data.detail}` : ''
          }`
        )

        return
      }

      setMessage(
        `❌ Login failed${data?.detail ? `: ${data.detail}` : '.'}`
      )
    } catch (error) {
      console.error('LOGIN ERROR:', error)

      setLoggedIn(false)

      setMessage(
        '❌ Cannot connect to the backend. Make sure FastAPI is running on http://localhost:8000'
      )
    } finally {
      setLoading(false)
    }
  }

  // ==========================================
  // CREATE PROFILE
  // ==========================================

  const createProfile = async (e) => {
    e.preventDefault()

    if (!loggedIn) {
      setMessage('⚠️ Please login first.')
      setAuthMode('login')
      setPage('auth')
      return
    }

    setLoading(true)
    setMessage('Creating your profile...')

    try {
      const response = await fetch(`${API}/profile-summary`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          location_preference: location.trim(),
          skills: getSkillsArray(),
        }),
      })

      const data = await getResponseData(response)

      console.log('PROFILE STATUS:', response.status)
      console.log('PROFILE DATA:', data)

      if (response.ok) {
        setMessage('✅ Profile created successfully!')
        return
      }

      if (response.status === 401) {
        setLoggedIn(false)
        setMessage(
          '⚠️ Your login session has expired. Please login again.'
        )

        setPassword('')
        setAuthMode('login')
        setPage('auth')

        return
      }

      setMessage(
        `❌ Could not create profile${
          data?.detail ? `: ${data.detail}` : '.'
        }`
      )
    } catch (error) {
      console.error('PROFILE ERROR:', error)

      setMessage(
        '❌ Cannot connect to the backend. Make sure FastAPI is running on http://localhost:8000'
      )
    } finally {
      setLoading(false)
    }
  }

  // ==========================================
  // LOGOUT
  // ==========================================

  const handleLogout = async () => {
    try {
      await fetch(`${API}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      })
    } catch (error) {
      console.log('Logout error:', error)
    }

    setLoggedIn(false)
    setPassword('')
    setMessage('You have been logged out.')
    setPage('home')
  }

  // ==========================================
  // REQUIRE LOGIN
  // ==========================================

  const requireLogin = (targetPage) => {
    if (!loggedIn) {
      setAuthMode('login')
      setMessage('⚠️ Please login first to use this feature.')
      setPage('auth')
      return
    }

    setMessage('')
    setPage(targetPage)
  }

  // ==========================================
  // INTERNSHIP DATA
  // ==========================================

  const internshipData = [
    {
      id: 1,
      title: 'Python Developer Intern',
      company: 'Software Development Company',
      location: 'Hyderabad',
      skills: ['python', 'git', 'sql'],
      icon: '💻',
    },
    {
      id: 2,
      title: 'Machine Learning Intern',
      company: 'AI Technology Company',
      location: 'Hyderabad',
      skills: ['python', 'machine learning', 'pandas'],
      icon: '🤖',
    },
    {
      id: 3,
      title: 'Data Science Intern',
      company: 'Data Analytics Company',
      location: 'Bangalore',
      skills: ['python', 'machine learning', 'sql', 'pandas'],
      icon: '📊',
    },
    {
      id: 4,
      title: 'Frontend Developer Intern',
      company: 'Technology Startup',
      location: 'Hyderabad',
      skills: ['javascript', 'react', 'html', 'css'],
      icon: '🌐',
    },
    {
      id: 5,
      title: 'AI Intern',
      company: 'Artificial Intelligence Company',
      location: 'Bangalore',
      skills: ['python', 'machine learning', 'artificial intelligence'],
      icon: '🧠',
    },
  ]

  const matchedInternships = useMemo(() => {
    const userSkills = getSkillsArray().map((skill) =>
      skill.toLowerCase()
    )

    const preferredLocation = location.trim().toLowerCase()

    const scored = internshipData.map((job) => {
      let score = 0

      const matchingSkills = job.skills.filter((jobSkill) =>
        userSkills.some(
          (userSkill) =>
            userSkill.includes(jobSkill) ||
            jobSkill.includes(userSkill)
        )
      )

      score += matchingSkills.length * 20

      if (
        preferredLocation &&
        job.location.toLowerCase().includes(preferredLocation)
      ) {
        score += 30
      }

      return {
        ...job,
        score,
        matchingSkills,
      }
    })

    return scored.sort((a, b) => b.score - a.score)
  }, [skills, location])

  // ==========================================
  // SKILL GAP
  // ==========================================

  const recommendedSkills = [
    'Python',
    'SQL',
    'Git',
    'Data Structures',
    'Machine Learning',
    'Communication',
    'Problem Solving',
  ]

  const currentSkillsLower = getSkillsArray().map((skill) =>
    skill.toLowerCase()
  )

  const skillGaps = recommendedSkills.filter(
    (skill) =>
      !currentSkillsLower.some(
        (current) =>
          current.includes(skill.toLowerCase()) ||
          skill.toLowerCase().includes(current)
      )
  )

  // ==========================================
  // INTERVIEW QUESTIONS
  // ==========================================

  const interviewQuestions = {
    Technical: [
      {
        question:
          'What is the difference between a list and a tuple in Python?',
        answer:
          'A list is mutable, while a tuple is immutable. Lists use square brackets and tuples use parentheses.',
      },
      {
        question:
          'What is the difference between == and = in Python?',
        answer:
          '= is used for assignment, while == is used to compare two values.',
      },
      {
        question:
          'What is a function in Python?',
        answer:
          'A function is a reusable block of code designed to perform a particular task.',
      },
    ],

    'Machine Learning': [
      {
        question:
          'Explain the difference between supervised and unsupervised learning.',
        answer:
          'Supervised learning uses labelled data, while unsupervised learning finds patterns in unlabelled data.',
      },
      {
        question:
          'What is overfitting in machine learning?',
        answer:
          'Overfitting happens when a model learns the training data too closely and performs poorly on unseen data.',
      },
      {
        question:
          'What is the purpose of train-test splitting?',
        answer:
          'It separates data used to train the model from data used to evaluate its performance on unseen examples.',
      },
    ],

    Behavioral: [
      {
        question:
          'Tell me about yourself and your career goals.',
        answer:
          'Give a short introduction covering your education, technical skills, projects, internships and your career goal.',
      },
      {
        question:
          'Why should we select you for this internship?',
        answer:
          'Explain your relevant skills, projects, willingness to learn and how you can contribute to the organization.',
      },
      {
        question:
          'Tell me about a challenge you faced in a project.',
        answer:
          'Describe the problem, what you did to solve it, the result and what you learned.',
      },
    ],
  }

  const currentInterviewQuestions =
    selectedInterviewType
      ? interviewQuestions[selectedInterviewType]
      : []

  const currentQuestion =
    currentInterviewQuestions.length > 0
      ? currentInterviewQuestions[interviewIndex %
          currentInterviewQuestions.length]
      : null

  const startInterview = (type) => {
    setSelectedInterviewType(type)
    setInterviewIndex(0)
    setMessage('')
  }

  const nextInterviewQuestion = () => {
    if (!selectedInterviewType) {
      setMessage('⚠️ Please select an interview category first.')
      return
    }

    setInterviewIndex(
      (previous) =>
        (previous + 1) %
        interviewQuestions[selectedInterviewType].length
    )

    setMessage('')
  }

  // ==========================================
  // RESUME ANALYSIS
  // ==========================================

  const analyzeResume = () => {
    if (!resumeFile) {
      setMessage('⚠️ Please select a resume first.')
      return
    }

    setResumeAnalyzed(true)

    setMessage(
      '✅ Resume uploaded successfully. Your resume analysis results are displayed below.'
    )
  }

  // ==========================================
  // UI
  // ==========================================

  return (
    <div className="app">

      {/* NAVBAR */}

      <nav className="navbar">

        <div
          className="logo"
          onClick={() => goTo('home')}
          style={{ cursor: 'pointer' }}
        >
          🚀 CareerCompanion
        </div>

        <div className="nav-links">

          <button onClick={() => goTo('home')}>
            Home
          </button>

          <button
            onClick={() => {
              if (loggedIn) {
                goTo('profile')
              } else {
                setAuthMode('login')
                setMessage('')
                goTo('auth')
              }
            }}
          >
            Profile
          </button>

          <button onClick={() => goTo('jobs')}>
            Internships
          </button>

          <button onClick={() => goTo('about')}>
            About
          </button>

          {!loggedIn ? (
            <button
              className="nav-login"
              onClick={() => {
                setAuthMode('login')
                setMessage('')
                goTo('auth')
              }}
            >
              Login
            </button>
          ) : (
            <button
              className="nav-login"
              onClick={handleLogout}
            >
              Logout
            </button>
          )}

        </div>
      </nav>

      <main>

        {/* HOME */}

        {page === 'home' && (
          <section className="hero-section">

            <div className="hero-content">

              <p className="tag">
                AI-POWERED CAREER ASSISTANT
              </p>

              <h1>
                Find the right
                <span> Internship </span>
                for your future.
              </h1>

              <p className="hero-text">
                AI Career Companion helps students discover
                internships, analyze their skills, improve
                resumes and prepare for interviews.
              </p>

              <div className="hero-buttons">

                <button
                  className="primary-btn"
                  onClick={() => {
                    if (loggedIn) {
                      goTo('profile')
                    } else {
                      setAuthMode('login')
                      goTo('auth')
                    }
                  }}
                >
                  {loggedIn ? 'Create My Profile' : 'Get Started'}
                </button>

                <button
                  className="secondary-btn"
                  onClick={() => goTo('jobs')}
                >
                  Explore Internships
                </button>

              </div>

            </div>

            <div className="hero-card">

              <div className="robot">
                🤖
              </div>

              <h2>
                Your AI Career Companion
              </h2>

              <p>
                Match • Improve • Prepare • Apply
              </p>

              <div className="feature-mini">
                <span>✓</span>
                Internship Matching
              </div>

              <div className="feature-mini">
                <span>✓</span>
                Skill Gap Analysis
              </div>

              <div className="feature-mini">
                <span>✓</span>
                Resume Assistance
              </div>

              <div className="feature-mini">
                <span>✓</span>
                Interview Preparation
              </div>

            </div>

          </section>
        )}

        {/* AUTH */}

        {page === 'auth' && (
          <section className="profile-section">

            <div className="section-heading">

              <p className="tag">
                {authMode === 'login'
                  ? 'WELCOME BACK'
                  : 'GET STARTED'}
              </p>

              <h2>
                {authMode === 'login'
                  ? 'Login to Career Companion'
                  : 'Create Your Account'}
              </h2>

              <p>
                {authMode === 'login'
                  ? 'Login to access your career profile and internship recommendations.'
                  : 'Create your account and start your internship journey.'}
              </p>

            </div>

            <form
              className="profile-form"
              onSubmit={
                authMode === 'login'
                  ? handleLogin
                  : handleSignup
              }
            >

              {authMode === 'signup' && (
                <div className="form-group">

                  <label>Name</label>

                  <input
                    type="text"
                    placeholder="Enter your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />

                </div>
              )}

              <div className="form-group">

                <label>Email</label>

                <input
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />

              </div>

              <div className="form-group">

                <label>Password</label>

                <input
                  type="password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />

              </div>

              {authMode === 'signup' && (
                <>
                  <div className="form-group">

                    <label>
                      Preferred Location
                    </label>

                    <input
                      type="text"
                      placeholder="Example: Hyderabad, Bangalore"
                      value={location}
                      onChange={(e) =>
                        setLocation(e.target.value)
                      }
                      required
                    />

                  </div>

                  <div className="form-group">

                    <label>
                      Skills
                    </label>

                    <input
                      type="text"
                      placeholder="Python, Machine Learning, SQL"
                      value={skills}
                      onChange={(e) =>
                        setSkills(e.target.value)
                      }
                      required
                    />

                    <small>
                      Separate multiple skills using commas.
                    </small>

                  </div>
                </>
              )}

              <button
                type="submit"
                className="primary-btn submit-btn"
                disabled={loading}
              >
                {loading
                  ? 'Please wait...'
                  : authMode === 'login'
                    ? 'Login'
                    : 'Create Account'}
              </button>

              {message && (
                <p className="message">
                  {message}
                </p>
              )}

            </form>

            <div className="auth-switch">

              {authMode === 'login' ? (
                <p>
                  Don't have an account?{' '}

                  <button
                    onClick={() => {
                      setAuthMode('signup')
                      setMessage('')
                      setPassword('')
                    }}
                  >
                    Sign Up
                  </button>
                </p>
              ) : (
                <p>
                  Already have an account?{' '}

                  <button
                    onClick={() => {
                      setAuthMode('login')
                      setMessage('')
                      setPassword('')
                    }}
                  >
                    Login
                  </button>
                </p>
              )}

            </div>

          </section>
        )}

        {/* PROFILE */}

        {page === 'profile' && (
          <section className="profile-section">

            <div className="section-heading">

              <p className="tag">
                YOUR PROFILE
              </p>

              <h2>
                Create Your Career Profile
              </h2>

              <p>
                Add your skills and preferred location
                to get personalized career recommendations.
              </p>

            </div>

            {!loggedIn ? (

              <div className="login-required">

                <h3>
                  🔐 Login Required
                </h3>

                <p>
                  Please login before creating your
                  career profile.
                </p>

                <button
                  className="primary-btn"
                  onClick={() => {
                    setAuthMode('login')
                    goTo('auth')
                  }}
                >
                  Login
                </button>

              </div>

            ) : (

              <form
                className="profile-form"
                onSubmit={createProfile}
              >

                <div className="form-row">

                  <div className="form-group">

                    <label>Name</label>

                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                    />

                  </div>

                  <div className="form-group">

                    <label>Email</label>

                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />

                  </div>

                </div>

                <div className="form-group">

                  <label>
                    Preferred Location
                  </label>

                  <input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    required
                  />

                </div>

                <div className="form-group">

                  <label>
                    Skills
                  </label>

                  <input
                    type="text"
                    value={skills}
                    onChange={(e) => setSkills(e.target.value)}
                    required
                  />

                  <small>
                    Separate multiple skills using commas.
                  </small>

                </div>

                <button
                  type="submit"
                  className="primary-btn submit-btn"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Create Profile'}
                </button>

                {message && (
                  <p className="message">
                    {message}
                  </p>
                )}

              </form>

            )}

          </section>
        )}

        {/* FEATURES */}

        {page === 'jobs' && (
          <section className="jobs-section">

            <div className="section-heading">

              <p className="tag">
                AI CAREER FEATURES
              </p>

              <h2>
                Everything You Need for Your
                Internship Journey
              </h2>

              <p>
                Your AI Career Companion brings internship
                discovery and career preparation into one platform.
              </p>

            </div>

            <div className="feature-grid">

              <div
                className="feature-card"
                onClick={() => requireLogin('matching')}
                style={{ cursor: 'pointer' }}
              >
                <div className="feature-icon">🎯</div>

                <h3>
                  Internship Matching
                </h3>

                <p>
                  Find internship opportunities based on
                  your skills, profile and preferred location.
                </p>

                <button
                  className="secondary-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    requireLogin('matching')
                  }}
                >
                  Explore Matching
                </button>
              </div>

              <div
                className="feature-card"
                onClick={() => requireLogin('resume')}
                style={{ cursor: 'pointer' }}
              >
                <div className="feature-icon">📄</div>

                <h3>
                  Resume Analysis
                </h3>

                <p>
                  Upload your resume and get useful
                  resume insights.
                </p>

                <button
                  className="secondary-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    requireLogin('resume')
                  }}
                >
                  Analyze Resume
                </button>
              </div>

              <div
                className="feature-card"
                onClick={() => requireLogin('skillgap')}
                style={{ cursor: 'pointer' }}
              >
                <div className="feature-icon">📊</div>

                <h3>
                  Skill Gap Analysis
                </h3>

                <p>
                  Identify skills you need to improve
                  for your target internship roles.
                </p>

                <button
                  className="secondary-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    requireLogin('skillgap')
                  }}
                >
                  Check Skill Gap
                </button>
              </div>

              <div
                className="feature-card"
                onClick={() => requireLogin('interview')}
                style={{ cursor: 'pointer' }}
              >
                <div className="feature-icon">🎤</div>

                <h3>
                  Interview Preparation
                </h3>

                <p>
                  Practice technical and behavioral
                  interview questions.
                </p>

                <button
                  className="secondary-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    requireLogin('interview')
                  }}
                >
                  Start Preparation
                </button>
              </div>

            </div>

          </section>
        )}

        {/* MATCHING */}

        {page === 'matching' && (
          <section className="profile-section">

            <div className="section-heading">

              <p className="tag">
                INTERNSHIP MATCHING
              </p>

              <h2>
                Internships Matched to Your Profile
              </h2>

              <p>
                Matching is based on your skills and
                preferred location.
              </p>

            </div>

            <div className="feature-grid">

              {matchedInternships.map((job) => (
                <div
                  className="feature-card"
                  key={job.id}
                >

                  <div className="feature-icon">
                    {job.icon}
                  </div>

                  <h3>
                    {job.title}
                  </h3>

                  <p>
                    {job.company}
                  </p>

                  <p>
                    📍 {job.location}
                  </p>

                  <p>
                    <strong>
                      Match Score: {Math.min(job.score, 100)}%
                    </strong>
                  </p>

                  {job.matchingSkills.length > 0 && (
                    <p>
                      ✓ Matching skills:{' '}
                      {job.matchingSkills.join(', ')}
                    </p>
                  )}

                </div>
              ))}

            </div>

            <button
              className="primary-btn"
              onClick={() => goTo('jobs')}
            >
              ← Back to Features
            </button>

          </section>
        )}

        {/* RESUME */}

        {page === 'resume' && (
          <section className="profile-section">

            <div className="section-heading">

              <p className="tag">
                RESUME ANALYSIS
              </p>

              <h2>
                Analyze Your Resume
              </h2>

              <p>
                Upload your resume to begin the
                resume analysis process.
              </p>

            </div>

            <div className="profile-form">

              <div className="form-group">

                <label>
                  Upload Resume
                </label>

                <input
                  type="file"
                  accept=".pdf,.doc,.docx"
                  onChange={(e) => {
                    setResumeFile(
                      e.target.files[0] || null
                    )
                    setResumeAnalyzed(false)
                    setMessage('')
                  }}
                />

              </div>

              {resumeFile && (
                <p className="message">
                  📄 Selected file:{' '}
                  <strong>{resumeFile.name}</strong>
                </p>
              )}

              <button
                className="primary-btn submit-btn"
                onClick={analyzeResume}
              >
                Analyze Resume
              </button>

              {message && (
                <p className="message">
                  {message}
                </p>
              )}

              {resumeAnalyzed && (
                <div className="feature-grid">

                  <div className="feature-card">

                    <div className="feature-icon">
                      📄
                    </div>

                    <h3>
                      Resume Status
                    </h3>

                    <p>
                      Resume selected successfully.
                    </p>

                  </div>

                  <div className="feature-card">

                    <div className="feature-icon">
                      💡
                    </div>

                    <h3>
                      Skills to Highlight
                    </h3>

                    <p>
                      {skills ||
                        'Add skills to your profile for personalized suggestions.'}
                    </p>

                  </div>

                  <div className="feature-card">

                    <div className="feature-icon">
                      🎯
                    </div>

                    <h3>
                      Improvement Areas
                    </h3>

                    <p>
                      Consider highlighting projects,
                      internships, technical skills and
                      measurable achievements.
                    </p>

                  </div>

                </div>
              )}

              <button
                className="secondary-btn"
                onClick={() => goTo('jobs')}
              >
                ← Back to Features
              </button>

            </div>

          </section>
        )}

        {/* SKILL GAP */}

        {page === 'skillgap' && (
          <section className="profile-section">

            <div className="section-heading">

              <p className="tag">
                SKILL GAP ANALYSIS
              </p>

              <h2>
                Understand Your Skill Gaps
              </h2>

              <p>
                Compare your current skills with
                recommended internship skills.
              </p>

            </div>

            <div className="feature-grid">

              <div className="feature-card">

                <div className="feature-icon">
                  ✅
                </div>

                <h3>
                  Your Current Skills
                </h3>

                <p>
                  {skills || 'No skills added yet.'}
                </p>

              </div>

              <div className="feature-card">

                <div className="feature-icon">
                  📚
                </div>

                <h3>
                  Skills You Already Have
                </h3>

                <p>
                  {recommendedSkills
                    .filter(
                      (skill) =>
                        !skillGaps.includes(skill)
                    )
                    .join(', ') ||
                    'No recommended skills matched yet.'}
                </p>

              </div>

              <div className="feature-card">

                <div className="feature-icon">
                  ⚠️
                </div>

                <h3>
                  Skills to Improve
                </h3>

                <p>
                  {skillGaps.length > 0
                    ? skillGaps.join(', ')
                    : 'Excellent! No major skill gaps detected.'}
                </p>

              </div>

            </div>

            <button
              className="secondary-btn"
              onClick={() => goTo('jobs')}
            >
              ← Back to Features
            </button>

          </section>
        )}

        {/* INTERVIEW */}

        {page === 'interview' && (
          <section className="profile-section">

            <div className="section-heading">

              <p className="tag">
                INTERVIEW PREPARATION
              </p>

              <h2>
                Prepare for Your Interview
              </h2>

              <p>
                Select an interview category and
                start practicing.
              </p>

            </div>

            {!selectedInterviewType ? (

              <div className="feature-grid">

                <div
                  className="feature-card"
                  onClick={() =>
                    startInterview('Technical')
                  }
                  style={{ cursor: 'pointer' }}
                >

                  <div className="feature-icon">
                    💻
                  </div>

                  <h3>
                    Technical Question
                  </h3>

                  <p>
                    Practice Python and technical
                    interview questions.
                  </p>

                  <button className="secondary-btn">
                    Practice Technical
                  </button>

                </div>

                <div
                  className="feature-card"
                  onClick={() =>
                    startInterview('Machine Learning')
                  }
                  style={{ cursor: 'pointer' }}
                >

                  <div className="feature-icon">
                    🧠
                  </div>

                  <h3>
                    Machine Learning
                  </h3>

                  <p>
                    Practice machine learning
                    interview questions.
                  </p>

                  <button className="secondary-btn">
                    Practice ML
                  </button>

                </div>

                <div
                  className="feature-card"
                  onClick={() =>
                    startInterview('Behavioral')
                  }
                  style={{ cursor: 'pointer' }}
                >

                  <div className="feature-icon">
                    🗣️
                  </div>

                  <h3>
                    Behavioral Question
                  </h3>

                  <p>
                    Practice HR and behavioral
                    interview questions.
                  </p>

                  <button className="secondary-btn">
                    Practice Behavioral
                  </button>

                </div>

              </div>

            ) : (

              <div className="profile-form">

                <h2>
                  {selectedInterviewType} Interview
                </h2>

                <div className="feature-card">

                  <div className="feature-icon">
                    🎤
                  </div>

                  <h3>
                    Question {interviewIndex + 1}
                  </h3>

                  <p>
                    {currentQuestion?.question}
                  </p>

                </div>

                <div className="feature-card">

                  <h3>
                    Suggested Answer
                  </h3>

                  <p>
                    {currentQuestion?.answer}
                  </p>

                </div>

                <button
                  className="primary-btn"
                  onClick={nextInterviewQuestion}
                >
                  Next Question →
                </button>

                <button
                  className="secondary-btn"
                  onClick={() => {
                    setSelectedInterviewType(null)
                    setInterviewIndex(0)
                  }}
                >
                  Choose Another Category
                </button>

              </div>

            )}

            {message && (
              <p className="message">
                {message}
              </p>
            )}

            <br />

            <button
              className="secondary-btn"
              onClick={() => goTo('jobs')}
            >
              ← Back to Features
            </button>

          </section>
        )}

        {/* ABOUT */}

        {page === 'about' && (
          <section className="profile-section">

            <div className="section-heading">

              <p className="tag">
                ABOUT THE PROJECT
              </p>

              <h2>
                AI Career Companion Agent
              </h2>

              <p>
                An AI-powered platform designed to help
                students discover internships, understand
                skill gaps, improve resumes and prepare
                for interviews.
              </p>

            </div>

            <div className="feature-grid">

              <div className="feature-card">

                <div className="feature-icon">
                  🤖
                </div>

                <h3>
                  AI Assistance
                </h3>

                <p>
                  Personalized career guidance using
                  AI-powered features.
                </p>

              </div>

              <div className="feature-card">

                <div className="feature-icon">
                  💼
                </div>

                <h3>
                  Career Opportunities
                </h3>

                <p>
                  Helps students discover suitable
                  internship opportunities.
                </p>

              </div>

              <div className="feature-card">

                <div className="feature-icon">
                  🎓
                </div>

                <h3>
                  Student Focused
                </h3>

                <p>
                  Designed especially for students
                  beginning their professional journey.
                </p>

              </div>

            </div>

          </section>
        )}

      </main>

      {/* FOOTER */}

      <footer>

        <h3>
          🚀 AI Career Companion
        </h3>

        <p>
          AI-powered internship matching and
          career preparation platform.
        </p>

        <p className="copyright">
          © 2026 AI Career Companion Agent
        </p>

      </footer>

    </div>
  )
}

export default App