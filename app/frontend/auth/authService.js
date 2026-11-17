import { authConfig } from "./authConfig.js";

const poolData = {
  UserPoolId: authConfig.USER_POOL_ID,
  ClientId: authConfig.CLIENT_ID,
};

const isLocal = () => authConfig.PROVIDER !== "cognito";

function saveSession(email, idToken) {
  localStorage.setItem("userEmail", email);
  localStorage.setItem("idToken", idToken);
  localStorage.removeItem("accessToken");
}

async function localAuth(path, email, password) {
  const res = await fetch(`${authConfig.API_BASE_URL}/auth/local/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong. Please try again.");
  saveSession(data.email, data.id_token);
  return data;
}

// Whether a new account needs an emailed confirmation code before logging in.
export const needsEmailConfirmation = () => !isLocal();

function getUserPool() {
  const { CognitoUserPool } = window.AmazonCognitoIdentity;
  return new CognitoUserPool(poolData);
}

export const signUp = (email, password) => {
  if (isLocal()) return localAuth("signup", email, password);
  return new Promise((resolve, reject) => {
    getUserPool().signUp(email, password, [], null, (err, result) => {
      if (err) return reject(err);
      resolve(result.user);
    });
  });
};

export const confirmSignup = (email, code) => {
  return new Promise((resolve, reject) => {
    const { CognitoUser } = window.AmazonCognitoIdentity;
    const user = new CognitoUser({ Username: email, Pool: getUserPool() });
    user.confirmRegistration(code, true, (err, result) => {
      if (err) return reject(err);
      resolve(result);
    });
  });
};

export const signIn = (email, password) => {
  if (isLocal()) return localAuth("login", email, password);
  return new Promise((resolve, reject) => {
    const { AuthenticationDetails, CognitoUser } = window.AmazonCognitoIdentity;

    const authDetails = new AuthenticationDetails({ Username: email, Password: password });
    const user = new CognitoUser({ Username: email, Pool: getUserPool() });

    user.authenticateUser(authDetails, {
      onSuccess: (session) => {
        localStorage.setItem("userEmail", email);
        localStorage.setItem("accessToken", session.getAccessToken().getJwtToken());
        localStorage.setItem("idToken", session.getIdToken().getJwtToken());
        resolve(session);
      },
      onFailure: reject,
    });
  });
};

export const signOut = () => {
  if (!isLocal()) {
    const user = getUserPool().getCurrentUser();
    if (user) user.signOut();
  }
  localStorage.clear();
};

export const federatedSignIn = (provider) => {
  const url =
    `https://${authConfig.COGNITO_DOMAIN}/oauth2/authorize?` +
    `identity_provider=${provider}&response_type=code` +
    `&client_id=${authConfig.CLIENT_ID}&redirect_uri=${authConfig.REDIRECT_URI}`;
  window.location.href = url;
};

export const getValidIdToken = () => {
  if (isLocal()) {
    return Promise.resolve(localStorage.getItem("idToken") || null);
  }
  return new Promise((resolve) => {
    const user = getUserPool().getCurrentUser();
    if (!user) {
      return resolve(localStorage.getItem("idToken") || localStorage.getItem("accessToken") || null);
    }
    user.getSession((err, session) => {
      if (err || !session || !session.isValid()) {
        return resolve(localStorage.getItem("idToken") || localStorage.getItem("accessToken") || null);
      }
      const token = session.getIdToken().getJwtToken();
      localStorage.setItem("idToken", token);
      resolve(token);
    });
  });
};