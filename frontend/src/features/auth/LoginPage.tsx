import { FormEvent, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clearAuthTokens, getAccessToken, getRefreshToken, setAccessToken, setRefreshToken } from '../../shared/auth/tokenStorage';
import { login, restoreSession } from './authApi';
import { loginPageContent } from './loginContent';
import { usePublicSettings } from '../settings/usePublicSettings';

function EyeIcon({ hidden }: { hidden: boolean }) {
  if (hidden) {
    return (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M1.8 10s3-5 8.2-5 8.2 5 8.2 5-3 5-8.2 5-8.2-5-8.2-5Z" />
        <circle cx="10" cy="10" r="2.2" />
        <path d="m3 17 14-14" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M1.8 10s3-5 8.2-5 8.2 5 8.2 5-3 5-8.2 5-8.2-5-8.2-5Z" />
      <circle cx="10" cy="10" r="2.2" />
    </svg>
  );
}

function userSafeLoginError(code: string | undefined, fallbackMessage: string): string {
  if (code === 'invalid_credentials') {
    return 'Thông tin đăng nhập chưa đúng. Vui lòng nhập lại mật khẩu.';
  }
  if (code === 'account_already_logged_in') {
    return 'Tài khoản đang có phiên đăng nhập khác. Nếu đây là cùng máy thi vừa bị tắt trình duyệt, vui lòng thử khôi phục phiên hoặc liên hệ giám thị.';
  }
  return fallbackMessage;
}

function FormFrameLogo({
  initials,
  logoAlt,
  logoImageSrc,
}: {
  initials: string;
  logoAlt: string;
  logoImageSrc?: string | null;
}) {
  if (logoImageSrc) {
    return <img className="form-frame-logo-image" src={logoImageSrc} alt={logoAlt} />;
  }

  return (
    <span className="form-frame-logo-text" aria-label={logoAlt}>
      {initials}
    </span>
  );
}

export function LoginPage() {
  const navigate = useNavigate();
  const content = loginPageContent;
  const { settings } = usePublicSettings();
  const passwordInputRef = useRef<HTMLInputElement | null>(null);
  const submittingRef = useRef(false);
  const restoringRef = useRef(false);
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRestoringSession, setIsRestoringSession] = useState(() => !getAccessToken() && Boolean(getRefreshToken()));
  const [restoreMessage, setRestoreMessage] = useState<string | null>(null);
  const [canRestoreSession, setCanRestoreSession] = useState(() => Boolean(getRefreshToken()));
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  useEffect(() => {
    const accessToken = getAccessToken();
    const refreshToken = getRefreshToken();

    setCanRestoreSession(Boolean(refreshToken));

    if (accessToken) {
      navigate('/dashboard', { replace: true });
      return;
    }

    if (refreshToken) {
      void handleRestoreSession();
    }
  }, [navigate]);

  function resetPasswordField() {
    setPassword('');
    setShowPassword(false);
    queueMicrotask(() => {
      passwordInputRef.current?.focus();
    });
  }

  async function handleRestoreSession() {
    if (restoringRef.current || submittingRef.current) {
      return;
    }

    restoringRef.current = true;
    setIsRestoringSession(true);
    setRestoreMessage(null);
    setError(null);
    setErrorCode(null);

    try {
      const response = await restoreSession();

      if (!response.ok) {
        clearAuthTokens();
        setCanRestoreSession(false);
        setRestoreMessage('Phiên đăng nhập trước không còn hiệu lực. Vui lòng đăng nhập lại.');
        return;
      }

      setCanRestoreSession(Boolean(getRefreshToken()));
      navigate('/dashboard', { replace: true });
    } catch {
      clearAuthTokens();
      setCanRestoreSession(false);
      setRestoreMessage('Phiên đăng nhập trước không còn hiệu lực. Vui lòng đăng nhập lại.');
    } finally {
      restoringRef.current = false;
      setIsRestoringSession(false);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submittingRef.current || restoringRef.current) {
      return;
    }

    submittingRef.current = true;
    setRestoreMessage(null);
    setError(null);
    setErrorCode(null);
    setIsSubmitting(true);
 
    try {
      const response = await login(identifier, password);

      if (!response.ok) {
        setCanRestoreSession(Boolean(getRefreshToken()));
        setErrorCode(response.error?.code ?? 'request_failed');
        setError(userSafeLoginError(response.error?.code, response.error?.message || content.form.genericError));
        resetPasswordField();
        return;
      }

      setAccessToken(response.data.access_token);
      setRefreshToken(response.data.refresh_token);
      navigate('/dashboard');
    } catch {
      setErrorCode('network_error');
      setError(content.form.genericError);
      resetPasswordField();
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <header className="login-page-top-bar" aria-label={settings.academy_name || content.brand.name}>
        <div className="login-page-bar-inner" style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <FormFrameLogo
              initials={content.brand.initials}
              logoAlt={settings.academy_name || content.brand.logoAlt}
              logoImageSrc={settings.portal_logo_url || content.brand.logoImageSrc}
            />
            <span style={{ color: '#ffffff', fontWeight: 700, fontSize: '1.2rem' }} data-testid="academy-name">
              {settings.academy_name || content.brand.name}
            </span>
          </div>
        </div>
      </header>

      <section className="login-panel" aria-labelledby="login-title">
        <div className="form-frame">
          <div className="form-frame-body">
            <div className="login-panel-header">
              <p className="eyebrow">{content.form.eyebrow}</p>
              <h2 id="login-title">{content.form.title}</h2>
            </div>

            {isRestoringSession ? (
              <p className="form-error" role="status">
                Đang khôi phục phiên đăng nhập...
              </p>
            ) : (
              <form className="login-form" onSubmit={onSubmit}>
                <label htmlFor="identifier">
                  {content.form.identifierLabel}
                  <input
                    id="identifier"
                    name="identifier"
                    type="text"
                    value={identifier}
                    onChange={(event) => {
                      setIdentifier(event.target.value);
                      setPassword('');
                      setShowPassword(false);
                      setRestoreMessage(null);
                      setError(null);
                      setErrorCode(null);
                    }}
                    autoComplete="username"
                    placeholder={content.form.identifierPlaceholder}
                    required
                  />
                </label>

                <label htmlFor="password">
                  {content.form.passwordLabel}
                  <div className="password-field">
                    <input
                      ref={passwordInputRef}
                      id="password"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(event) => {
                        setPassword(event.target.value);
                        if (restoreMessage || errorCode === 'invalid_credentials' || errorCode === 'account_already_logged_in') {
                          setRestoreMessage(null);
                          setError(null);
                          setErrorCode(null);
                        }
                      }}
                      autoComplete="current-password"
                      placeholder={content.form.passwordPlaceholder}
                      required
                    />
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={showPassword ? content.form.hidePasswordLabel : content.form.showPasswordLabel}
                      title={showPassword ? content.form.hidePasswordLabel : content.form.showPasswordLabel}
                      onClick={() => setShowPassword((current) => !current)}
                    >
                      <span aria-hidden="true" style={{ display: 'inline-flex', width: 16, height: 16 }}>
                        <EyeIcon hidden={showPassword} />
                      </span>
                    </button>
                  </div>
                </label>

                {restoreMessage ? (
                  <p className="form-error" role="alert">
                    {restoreMessage}
                  </p>
                ) : null}

                {error ? (
                  <p className="form-error" role="alert">
                    {error}
                  </p>
                ) : null}

                {errorCode === 'account_already_logged_in' ? (
                  canRestoreSession ? (
                    <button className="primary-button" type="button" onClick={() => void handleRestoreSession()}>
                      Khôi phục phiên đăng nhập
                    </button>
                  ) : (
                    <p className="form-error">Nếu đây không phải cùng máy thi còn phiên hoạt động, vui lòng liên hệ giám thị hoặc quản trị viên.</p>
                  )
                ) : null}

                <button className="primary-button" type="submit" disabled={isSubmitting || isRestoringSession}>
                  {isSubmitting ? content.form.submittingLabel : content.form.submitLabel}
                </button>
              </form>
            )}
          </div>
        </div>
      </section>

      <footer className="login-page-footer">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'center' }}>
          <div>{content.frame.footerText}</div>
          {(settings.support_email || settings.support_hotline) && (
            <div style={{ fontSize: '0.85em', opacity: 0.9, fontWeight: 'normal' }} data-testid="support-info">
              Hỗ trợ kỹ thuật: {settings.support_email ? `Email: ${settings.support_email}` : ''}
              {settings.support_email && settings.support_hotline ? ' | ' : ''}
              {settings.support_hotline ? `Hotline: ${settings.support_hotline}` : ''}
            </div>
          )}
        </div>
      </footer>
    </main>
  );
}

