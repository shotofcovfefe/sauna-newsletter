"use client"

import { XMarkIcon } from '@heroicons/react/24/outline'

interface NewsletterSignupProps {
  isOpen: boolean
  onClose: () => void
}

export default function NewsletterSignup({ isOpen, onClose }: NewsletterSignupProps) {
  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="bg-white rounded-xl shadow-2xl overflow-hidden w-full max-w-lg h-[80vh] relative z-10"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          aria-label="Close newsletter signup"
          className="absolute top-3 right-3 text-gray-500 hover:text-gray-700 p-2 rounded-full bg-white"
        >
          <XMarkIcon className="w-6 h-6" />
        </button>

        {/* Embedded Substack iframe */}
        <iframe
          src="https://thelondonsauna.substack.com/embed"
          className="w-full h-full"
          frameBorder="0"
          scrolling="no"
          title="Substack Newsletter Signup"
        />
      </div>
    </div>
  )
}
