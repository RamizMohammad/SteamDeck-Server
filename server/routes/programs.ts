import express from 'express';
import { ObjectId } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import { getUsersCollection, Program } from '../db/mongodb';
import { authMiddleware, AuthRequest } from '../utils/auth';

const router = express.Router();

router.get('/programs', authMiddleware, async (req: AuthRequest, res) => {
  try {
    const users = await getUsersCollection();
    const user = await users.findOne({ _id: new ObjectId(req.userId) });

    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json({ programs: user.programs || [] });
  } catch (error) {
    console.error('Get programs error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.post('/programs', authMiddleware, async (req: AuthRequest, res) => {
  try {
    const { name, iconUrl, exec, meta } = req.body;

    if (!name || !exec) {
      return res.status(400).json({ error: 'Name and exec are required' });
    }

    const newProgram: Program = {
      id: uuidv4(),
      name,
      iconUrl: iconUrl || '',
      exec,
      meta: meta || { source: 'user' },
      addedAt: new Date()
    };

    const users = await getUsersCollection();
    await users.updateOne(
      { _id: new ObjectId(req.userId) },
      {
        $push: {
          programs: newProgram,
          activityLog: {
            ts: new Date(),
            type: 'info',
            msg: `Added program: ${name}`,
            raw: newProgram
          }
        }
      }
    );

    res.json({ success: true, program: newProgram });
  } catch (error) {
    console.error('Add program error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

export default router;
