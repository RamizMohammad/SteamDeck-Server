import express from 'express';
import { ObjectId } from 'mongodb';
import { getUsersCollection, User } from '../db/mongodb';
import { hashPassword, verifyPassword, generateToken, authMiddleware, AuthRequest } from '../utils/auth';

const router = express.Router();

router.post('/auth', async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password are required' });
    }

    const users = await getUsersCollection();
    const existingUser = await users.findOne({ email });

    if (existingUser) {
      const isValid = await verifyPassword(password, existingUser.passwordHash);

      if (!isValid) {
        return res.status(401).json({ error: 'Wrong password' });
      }

      const token = generateToken(existingUser._id!.toString());
      const { passwordHash, ...userWithoutPassword } = existingUser;

      return res.json({
        token,
        user: userWithoutPassword
      });
    }

    const newUser: User = {
      email,
      passwordHash: await hashPassword(password),
      programsFetched: false,
      programs: [],
      activityLog: [{
        ts: new Date(),
        type: 'info',
        msg: 'Account created',
        raw: {}
      }],
      createdAt: new Date()
    };

    const result = await users.insertOne(newUser);
    const token = generateToken(result.insertedId.toString());

    const { passwordHash, ...userWithoutPassword } = newUser;

    res.json({
      token,
      user: { ...userWithoutPassword, _id: result.insertedId }
    });
  } catch (error) {
    console.error('Auth error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/me', authMiddleware, async (req: AuthRequest, res) => {
  try {
    const users = await getUsersCollection();
    const user = await users.findOne({ _id: new ObjectId(req.userId) });

    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    const { passwordHash, ...userWithoutPassword } = user;
    res.json(userWithoutPassword);
  } catch (error) {
    console.error('Get user error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

export default router;
