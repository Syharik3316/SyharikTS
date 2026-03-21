import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import styles from './Header.module.css';
import { useTheme } from '../../theme/ThemeProvider.jsx';
import { useAuth } from '../../context/AuthContext';

export default function Header() {
  const { pathname } = useLocation();
  const { user, logout, ready, bootstrapping } = useAuth();
  const isUploadPage = pathname === '/upload';
  const isAuthFlow =
    pathname === '/login' ||
    pathname.startsWith('/register') ||
    pathname === '/verify-email' ||
    pathname === '/reset-password' ||
    pathname === '/profile' ||
    pathname.startsWith('/profile/generations');
  const { theme, setTheme } = useTheme();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const settingsRef = useRef(null);
  const userMenuRef = useRef(null);

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  useEffect(() => {
    const handleOutsideClick = (event) => {
      const target = event.target;
      const outsideSettings = settingsRef.current && !settingsRef.current.contains(target);
      const outsideUserMenu = userMenuRef.current && !userMenuRef.current.contains(target);
      if (outsideSettings) setIsSettingsOpen(false);
      if (outsideUserMenu) setIsUserMenuOpen(false);
    };

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsSettingsOpen(false);
        setIsUserMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleEscape);
    };
  }, []);

  const toggleThemeClass = theme === 'dark' ? styles.dark : styles.light;
  const toggleEmoji = theme === 'dark' ? '🌙' : '☀️';

  const sessionReady = ready && !bootstrapping;

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.brandRow}>
          {isUploadPage || isAuthFlow ? (
            <Link className={styles.backLink} to="/">
              ← Назад
            </Link>
          ) : null}
          <div
            className={`${styles.logoWrap} ${
              isUploadPage || isAuthFlow ? styles.logoWrapWithBack : ''
            }`}
          >
            <Link className={styles.logoLink} to="/">
              <h1 className={styles.logo}>SyharikTS</h1>
            </Link>
          </div>
        </div>

        <div className={styles.centerNav}>
          {sessionReady && user ? (
            <Link className={`${styles.actionButton} ${styles.actionLink}`} to="/upload">
              Генерация
            </Link>
          ) : null}
        </div>

        <div className={styles.actions} aria-label="Авторизация">
          {sessionReady && user ? (
            <div className={styles.userMenuWrap} ref={userMenuRef}>
              <button
                type="button"
                className={styles.userBadgeButton}
                onClick={() => setIsUserMenuOpen((p) => !p)}
                aria-label="Открыть меню пользователя"
                aria-expanded={isUserMenuOpen}
                aria-controls="user-menu"
              >
                {user.login}
              </button>

              <div
                id="user-menu"
                className={`${styles.userMenu} ${isUserMenuOpen ? styles.userMenuOpen : ''}`}
                role="menu"
                aria-hidden={!isUserMenuOpen}
              >
                <Link
                  className={styles.userMenuItem}
                  to="/profile"
                  onClick={() => setIsUserMenuOpen(false)}
                  role="menuitem"
                >
                  Профиль
                </Link>
                <button
                  type="button"
                  className={styles.userMenuItem}
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    logout();
                  }}
                  role="menuitem"
                >
                  Выйти
                </button>
              </div>
            </div>
          ) : sessionReady ? (
            <>
              <Link className={`${styles.actionButton} ${styles.actionLink}`} to="/login">
                Вход
              </Link>
              <Link
                className={`${styles.actionButton} ${styles.actionLink}`}
                to="/register"
              >
                Регистрация
              </Link>
            </>
          ) : null}

          <div className={styles.settingsWrap} ref={settingsRef}>
            <button
              className={styles.settingsButton}
              type="button"
              aria-label="Настройки сайта"
              aria-expanded={isSettingsOpen}
              aria-controls="header-settings-menu"
              onClick={() => setIsSettingsOpen((prev) => !prev)}
            >
              ⚙
            </button>

            <div
              id="header-settings-menu"
              className={`${styles.settingsMenu} ${
                isSettingsOpen ? styles.settingsMenuOpen : ''
              }`}
              role="menu"
              aria-hidden={!isSettingsOpen}
            >
              <div className={styles.settingsItem}>
                <span className={styles.settingsLabel}>Тема</span>
                <button
                  className={`${styles.themeToggle} ${toggleThemeClass}`}
                  type="button"
                  onClick={toggleTheme}
                  role="switch"
                  aria-label="Сменить тему"
                  aria-checked={theme === 'light'}
                >
                  <span className={styles.themeEmoji} aria-hidden="true">
                    {toggleEmoji}
                  </span>
                  <span className={styles.themeTrack} aria-hidden="true">
                    <span className={styles.themeKnob} aria-hidden="true" />
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
