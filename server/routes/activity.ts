import express from 'express';
import { ObjectId } from 'mongodb';
import { getUsersCollection, ActivityLogEntry } from '../db/mongodb';
import { authMiddleware, AuthRequest } from '../utils/auth';

const router = express.Router();

router.get('/activity', authMiddleware, async (req: AuthRequest, res) => {
  try {
    const users = await getUsersCollection();
    const user = await users.findOne({ _id: new ObjectId(req.userId) });

    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json({ activityLog: user.activityLog || [] });
  } catch (error) {
    console.error('Get activity error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.post('/activity', authMiddleware, async (req: AuthRequest, res) => {
  try {
    const { type, msg, raw } = req.body;

    if (!type || !msg) {
      return res.status(400).json({ error: 'Type and message are required' });
    }

    const entry: ActivityLogEntry = {
      ts: new Date(),
      type,
      msg,
      raw: raw || {}
    };

    const users = await getUsersCollection();
    await users.updateOne(
      { _id: new ObjectId(req.userId) },
      { $push: { activityLog: entry } }
    );

    res.json({ success: true, entry });
  } catch (error) {
    console.error('Add activity error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

export default router;
