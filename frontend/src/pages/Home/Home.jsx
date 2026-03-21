import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import styles from './Home.module.css';

export default function Home() {
  const { user, ready, bootstrapping } = useAuth();
  const sessionReady = ready && !bootstrapping;
  const ctaTo = sessionReady && user ? '/upload' : '/login';
  const ctaLabel = sessionReady && user ? 'Перейти к генерации' : 'Войти и начать';

  return (
    <section className={styles.home} aria-label="Главная страница">
      <div className={styles.layout}>
        <div className={styles.left}>
          <h2 className={styles.title}>Генерация TypeScript-кода из файла произвольного формата</h2>
          <p className={styles.subtitle}>
            Превратите таблицы из CSV, Excel и PDF в готовый TypeScript-код за секунды с помощью ИИ
          </p>

          <Link className={styles.cta} to={ctaTo}>
            {ctaLabel} →
          </Link>
        </div>

        <div className={styles.right}>
          <table className={styles.gifTable} aria-label="GIF-анимация" tabIndex={0}>
            <tbody>
              <tr>
                <td className={styles.gifCell}>
                  <img className={styles.gifImage} src="/home.gif" alt="GIF" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <section
        className={styles.features}
        aria-labelledby="home-features-title"
      >
        <h2 id="home-features-title" className={styles.featuresTitle}>
          Наши возможности
        </h2>
        <ul className={styles.featuresGrid}>
          <li className={styles.featureCard}>
            <p className={styles.featureText}>
              Загрузка таблиц и документов: генерация TS-кода по примеру JSON-схемы выходных данных.
            </p>
          </li>
          <li className={styles.featureCard}>
            <p className={styles.featureText}>
              Автоматическое построение черновика схемы из файла перед генерацией.
            </p>
          </li>
          <li className={styles.featureCard}>
            <p className={styles.featureText}>
              Проверка сгенерированного кода в браузере: transpile TS → выполнение и просмотр JSON.
            </p>
          </li>
        </ul>
      </section>
    </section>
  );
}
