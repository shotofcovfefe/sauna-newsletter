'use client'

import { useState, FormEvent, useEffect } from 'react'
import { EnvelopeIcon, CheckCircleIcon, XMarkIcon } from '@heroicons/react/24/outline'

interface NewsletterSignupProps {
  isOpen: boolean
  onClose: () => void
}

export default function NewsletterSignup({ isOpen, onClose }: NewsletterSignupProps) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'unset'
    }
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [isOpen])

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setStatus('loading')
    setMessage('')

    try {
      // TODO: Replace with your actual newsletter signup endpoint
      // For now, we'll just simulate a successful submission
      await new Promise((resolve) => setTimeout(resolve, 1000))

      // Example: Send to a newsletter service
      // const response = await fetch('/api/newsletter/subscribe', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ email }),
      // })

      setStatus('success')
      setMessage('Thanks for subscribing! Check your email to confirm.')
      setEmail('')
    } catch (error) {
      setStatus('error')
      setMessage('Something went wrong. Please try again.')
      console.error('Newsletter signup error:', error)
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop - darkened background */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal Content */}
      <div
        className="bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-xl shadow-2xl p-6 md:p-8 max-w-lg w-full relative z-10 animate-in fade-in zoom-in duration-300"
        onClick={(e) => e.stopPropagation()}
        suppressHydrationWarning
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-white/70 hover:text-white transition-colors p-2 rounded-full hover:bg-white/10"
          aria-label="Close newsletter signup"
          suppressHydrationWarning
        >
          <XMarkIcon className="w-6 h-6" />
        </button>

        <div className="space-y-4 pr-8" suppressHydrationWarning>
          <div className="text-center" suppressHydrationWarning>
            <div className="bg-white/10 p-3 rounded-full inline-block mb-3" suppressHydrationWarning>
              <EnvelopeIcon className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold mb-2">Weekly Sauna Newsletter</h2>
            <p className="text-primary-100 text-sm">
              Get London's best sauna events, tips, and updates delivered every Thursday morning.
            </p>
          </div>

          {status === 'success' ? (
            <div className="bg-white/10 rounded-lg p-3 flex items-center gap-2">
              <CheckCircleIcon className="w-5 h-5 text-green-300 flex-shrink-0" />
              <p className="text-sm">{message}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-2">
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  required
                  disabled={status === 'loading'}
                  className="flex-1 min-w-0 px-3 py-2 rounded-lg bg-white/10 border border-white/20 placeholder-white/60 text-white text-sm focus:outline-none focus:ring-2 focus:ring-white/50 disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={status === 'loading'}
                  className="px-4 py-2 bg-white text-primary-700 font-semibold rounded-lg hover:bg-primary-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap text-sm"
                >
                  {status === 'loading' ? 'Subscribing...' : 'Subscribe'}
                </button>
              </div>

              {status === 'error' && (
                <p className="text-xs text-red-200">{message}</p>
              )}

              <p className="text-xs text-primary-200">
                We respect your privacy. Unsubscribe anytime.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
