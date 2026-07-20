import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const roleHome = (role) => (role === 'government' ? '/command' : '/citizen/fraud-shield');

const ProtectedRoute = ({ children, allowedRole }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#041E24] text-cyan-300">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRole && user.role && user.role !== allowedRole) {
    return <Navigate to={roleHome(user.role)} replace />;
  }

  return children;
};

export default ProtectedRoute;
