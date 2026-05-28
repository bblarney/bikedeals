import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  reset = () => this.setState({ error: null })

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-6 py-12">
        <div className="max-w-md bg-white border border-slate-200 rounded-xl p-6 text-center">
          <h1 className="text-lg font-semibold text-slate-900 mb-2">Something went wrong</h1>
          <p className="text-sm text-slate-500 mb-4">
            Try reloading the page. If it keeps happening, let us know.
          </p>
          <button
            onClick={() => { this.reset(); window.location.reload() }}
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors"
          >
            Reload
          </button>
        </div>
      </div>
    )
  }
}
